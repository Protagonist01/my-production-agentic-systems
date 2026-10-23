"""Trusted provisioning and loopback SIM workbench. No freight or message provider."""

import argparse
import getpass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import uvicorn
from agent_harness.local_services import Workspace
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from supply_chain.action_contracts import Shipment
from supply_chain.console_api import create_app
from supply_chain.console_auth import AuthStore, provision, setup_console
from supply_chain.console_contracts import IncidentContext, Principal
from supply_chain.console_service import ConsoleService
from supply_chain.notices import NoticeStore
from supply_chain.operations import OperationStore, enroll, setup
from supply_chain.source import read_alerts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    account = commands.add_parser("account")
    account.add_argument("--principal", type=Path, required=True)
    seed = commands.add_parser("seed-demo")
    seed.add_argument("--tenant", required=True)
    seed.add_argument("--event", required=True)
    seed.add_argument("--clock", required=True)
    context = commands.add_parser("context")
    context.add_argument("--input", type=Path, required=True)
    context.add_argument("--source-directory", type=Path)
    context.add_argument("--manifest-sha")
    context.add_argument("--alert-key")
    context.add_argument("--clock")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8877)
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
            with workspace.server().connect(trial.name) as admin:
                setup(admin, trial.name)
                setup_console(admin, trial.name)
            print('{"console":"ready","unit":"SIM","provider_calls":0}')
            return
        trial, server = workspace.load_trial(args.trial), workspace.server()
        if args.command == "account":
            user = Principal.model_validate_json(args.principal.read_bytes())
            password = getpass.getpass("New account password (15-128 characters): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("password confirmation differs")
            with server.connect(trial.name) as admin:
                provision(admin, user, password)
            print('{"account":"provisioned"}')
            return
        if args.command == "seed-demo":
            now = datetime.fromisoformat(args.clock)
            if now.utcoffset() is None:
                raise ValueError("aware explicit clock required")
            shipments = tuple(
                Shipment(
                    tenant_id=args.tenant,
                    shipment_id=f"{args.event}-shipment-{i}",
                    region="invented-region",
                    observed_at=now,
                    expires_at=now + timedelta(minutes=30),
                    estimated_delay_hours=delay,
                    facts_complete=i != 4,
                )
                for i, delay in enumerate((1, 4, 12, 8), 1)
            )
            with server.connect(trial.name) as admin:
                enroll(admin, args.event, shipments)
                value = IncidentContext(
                    tenant_id=args.tenant,
                    event_id=args.event,
                    label="Invented regional disruption",
                    source_kind="invented",
                )
                admin.execute(
                    "INSERT INTO supply_app.contexts VALUES(%s,%s,%s)",
                    (value.tenant_id, value.event_id, Jsonb(value.model_dump(mode="json"))),
                )
            print('{"demo":"enrolled","provenance":"invented","provider_calls":0}')
            return
        if args.command == "context":
            value = IncidentContext.model_validate_json(args.input.read_bytes())
            source_args = (args.source_directory, args.manifest_sha, args.alert_key, args.clock)
            if value.source_kind == "s1-public-observation":
                if not all(source_args):
                    raise ValueError("real context requires pinned S1 reader arguments")
                alerts = read_alerts(
                    args.source_directory,
                    args.manifest_sha,
                    datetime.fromisoformat(args.clock),
                    timedelta(seconds=value.max_alert_age_seconds),
                )
                alert = next((a for a in alerts if a.source_key == args.alert_key), None)
                if alert is None:
                    raise ValueError("current verified alert unavailable")
                value = value.model_copy(update={"alert": alert, "source_ref": args.manifest_sha})
            elif any(source_args):
                raise ValueError("invented context cannot claim S1 source arguments")
            with server.connect(trial.name) as admin:
                if (
                    admin.execute(
                        "SELECT 1 FROM supply.budgets WHERE tenant_id=%s AND event_id=%s",
                        (value.tenant_id, value.event_id),
                    ).fetchone()
                    is None
                ):
                    raise ValueError("enroll incident first")
                admin.execute(
                    "INSERT INTO supply_app.contexts VALUES(%s,%s,%s) "
                    "ON CONFLICT(tenant_id,event_id) DO UPDATE SET document=EXCLUDED.document",
                    (value.tenant_id, value.event_id, Jsonb(value.model_dump(mode="json"))),
                )
            print('{"context":"recorded","causal_join":"unverified"}')
            return
        if not 1024 <= args.port <= 65535:
            raise ValueError("unprivileged loopback port required")

        def connect() -> psycopg.Connection[Any]:
            return server.connect_trial(trial)

        service = ConsoleService(OperationStore(connect), NoticeStore(connect))
        app = create_app(
            service, AuthStore(connect), origin=f"http://127.0.0.1:{args.port}", trial_id=trial.name
        )
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            proxy_headers=False,
            access_log=False,
            limit_concurrency=16,
            timeout_keep_alive=5,
            log_level="warning",
        )
    except (ValidationError, ValueError, OSError, psycopg.Error) as error:
        parser.error(
            "Supply console operation failed: "
            + type(error).__name__
            + "; inspect private configuration"
        )


if __name__ == "__main__":
    main()
