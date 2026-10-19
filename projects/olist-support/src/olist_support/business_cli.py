"""Explicit private operator commands for the offline controlled Olist application."""

import argparse
import json
from contextlib import closing
from pathlib import Path
from typing import Any

import psycopg
from agent_harness.contracts import RunContext
from agent_harness.local_services import Workspace
from pydantic import ValidationError

from olist_support.business import BusinessStore, enroll, setup
from olist_support.business_contracts import CallerGrant
from olist_support.policy import ScenarioConfirmation
from olist_support.policy_cases import external, local_clock
from olist_support.views import OrderScope, OrderStore
from olist_support.workflow import FixedPlanner, IntentPlan, SupportWorkflow, WorkflowRequest
from olist_support.workflow_postgres import saver, setup_checkpoints


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    seed = commands.add_parser("enroll")
    seed.add_argument("--source-database", type=Path, required=True)
    seed.add_argument("--source-pin", required=True)
    seed.add_argument("--tenant", required=True)
    seed.add_argument("--order", required=True)
    seed.add_argument("--as-of-source-local", required=True)
    seed.add_argument("--confirmation", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--context", type=Path, required=True)
    run.add_argument("--request", type=Path, required=True)
    run.add_argument("--grant", type=Path, required=True)
    run.add_argument("--intent", choices=("refund", "status", "reship", "review"), required=True)
    run.add_argument("--requested-minor", type=int)
    run.add_argument("--run-limit-minor", type=int, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        workspace = Workspace(args.root.resolve())
        if args.command == "bootstrap":
            workspace.up()
            trial = (
                workspace.load_trial(args.trial)
                if workspace.trial_path(args.trial).exists()
                else workspace.create(args.trial)
            )
            server = workspace.server()
            with server.connect(trial.name) as admin:
                setup(admin, trial.name)
            with server.connect(trial.name) as admin:
                setup_checkpoints(admin, trial.name)
            print(json.dumps({"bootstrap": "ready", "business_unit": "SIM", "provider_calls": 0}))
            return
        trial, server = workspace.load_trial(args.trial), workspace.server()
        if args.command == "enroll":
            facts = (
                ScenarioConfirmation.model_validate_json(external(args.confirmation).read_bytes())
                if args.confirmation
                else None
            )
            with closing(
                OrderStore(args.source_database, expected_sha256=args.source_pin)
            ) as source:
                view = source.view(
                    OrderScope(args.tenant, frozenset((args.order,))),
                    tenant_id=args.tenant,
                    order_id=args.order,
                    as_of=local_clock(args.as_of_source_local),
                )
            with server.connect(trial.name) as admin:
                enroll(admin, view, facts)
            print(json.dumps({"enrolled_orders": 1, "business_unit": "SIM", "provider_calls": 0}))
            return
        context = RunContext.model_validate_json(external(args.context).read_bytes())
        if context.mode != "offline_fake":
            raise ValueError(
                "operator-selected intent CLI requires offline_fake; fresh models "
                "need explicit bounded-gateway composition"
            )
        request = WorkflowRequest.model_validate_json(external(args.request).read_bytes())
        grant = CallerGrant.model_validate_json(external(args.grant).read_bytes())
        plan = IntentPlan.model_validate(
            {"intent": args.intent, "requested_minor": args.requested_minor}
        )
        if type(args.run_limit_minor) is not int or not 0 <= args.run_limit_minor <= 2**63 - 1:
            raise ValueError("explicit nonnegative SIM run limit required")
        output = external(args.output)
        # Claim a new private artifact before any possible business action. An existing
        # output therefore cannot turn a successful commit into a misleading overwrite.
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            output.chmod(0o600)

            def connect() -> psycopg.Connection[Any]:
                return server.connect_trial(trial)

            with saver(connect) as checkpoints:
                result = SupportWorkflow(BusinessStore(connect), FixedPlanner(plan)).run(
                    context, request, grant, checkpoints, run_limit_minor=args.run_limit_minor
                )
            stream.write(result.canonical_json() + "\n")
        print(
            json.dumps(
                {"outcome": result.outcome, "private_result": str(output), "provider_calls": 0}
            )
        )
    except (ValidationError, ValueError, OSError, psycopg.Error) as error:
        # Schema/DB exceptions can embed source text or connection details. Keep the
        # command-line failure diagnostic typed; private artifacts remain local.
        parser.error(
            "operation failed: "
            + type(error).__name__
            + "; inspect private inputs and the operations runbook"
        )


if __name__ == "__main__":
    main()
