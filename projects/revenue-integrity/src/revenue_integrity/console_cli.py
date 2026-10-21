"""Trusted provisioning and loopback Revenue review service, never a live billing client."""

import argparse
import getpass
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
import uvicorn
from agent_harness.local_services import Workspace
from pydantic import ValidationError

from revenue_integrity.billing_access import BillingGrant
from revenue_integrity.billing_worlds import read_world
from revenue_integrity.console_api import create_app
from revenue_integrity.console_auth import AuthStore, provision, setup_console
from revenue_integrity.console_contracts import Principal, Wake
from revenue_integrity.console_service import ConsoleService
from revenue_integrity.operation_contracts import RevenueRecord
from revenue_integrity.operations import OperationStore, enroll, setup
from revenue_integrity.source_io import external


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    account = commands.add_parser("account")
    account.add_argument("--principal", type=Path, required=True)
    record = commands.add_parser("record")
    record.add_argument("--input", type=Path, required=True)
    seed = commands.add_parser("seed-world")
    seed.add_argument("--database", type=Path, required=True)
    seed.add_argument("--case-id", required=True)
    seed.add_argument("--tenant", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8876)
    serve.add_argument("--events-origin")
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
            with workspace.server().connect(trial.name) as admin:
                setup_console(admin, trial.name)
            print('{"console":"ready","unit":"SIM","provider_calls":0}')
            return
        trial, server = workspace.load_trial(args.trial), workspace.server()
        if args.command == "account":
            user = Principal.model_validate_json(external(args.principal).read_bytes())
            password = getpass.getpass("New account password (15–128 characters): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("password confirmation differs")
            with server.connect(trial.name) as admin:
                provision(admin, user, password)
            print('{"account":"provisioned"}')
            return
        if args.command == "record":
            value = RevenueRecord.model_validate_json(external(args.input).read_bytes())
            with server.connect(trial.name) as admin:
                enroll(admin, value)
            print('{"record":"enrolled"}')
            return
        if args.command == "seed-world":
            world = read_world(
                args.database,
                args.case_id,
                BillingGrant(
                    tenant_id=args.tenant,
                    actor_id="trusted-seed",
                    world_ids=(args.case_id,),
                    capabilities=("read",),
                ),
            )
            with server.connect(trial.name) as admin:
                existing = admin.execute(
                    "SELECT kind FROM revenue.records WHERE tenant_id=%s AND resource_id=%s",
                    (world.tenant_id, world.account_id),
                ).fetchone()
                if existing is None:
                    enroll(
                        admin,
                        RevenueRecord(
                            tenant_id=world.tenant_id,
                            resource_id=world.account_id,
                            kind="account",
                            note=" Constructed account ",
                        ),
                    )
                elif existing[0] != "account":
                    raise ValueError("account identity conflicts")
                enroll(
                    admin,
                    RevenueRecord(
                        tenant_id=world.tenant_id,
                        resource_id=world.case_id,
                        kind="invoice",
                        amount_minor=world.invoice.amount_minor,
                        account_id=world.account_id,
                        billing_input=world,
                    ),
                )
            print('{"world":"enrolled","source_kind":"synthetic"}')
            return
        if not 1024 <= args.port <= 65535:
            raise ValueError("unprivileged loopback port required")

        def connect() -> psycopg.Connection[Any]:
            return server.connect_trial(trial)

        auth = AuthStore(connect)
        service = ConsoleService(OperationStore(connect))
        publish = None
        client = None
        if args.events_origin:
            parsed = urlsplit(args.events_origin)
            if (
                parsed.scheme != "http"
                or parsed.hostname not in ("localhost", "127.0.0.1")
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in ("", "/")
            ):
                raise ValueError("loopback event service required")
            import inngest
            import inngest.fast_api

            from revenue_integrity.events import EventHandlers, build_functions, event_for

            signing = os.environ.get("INNGEST_SIGNING_KEY")
            event_key = os.environ.get("INNGEST_EVENT_KEY")
            if not signing or not event_key:
                raise ValueError("local event keys must be configured")
            client = inngest.Inngest(
                app_id="revenue-integrity",
                is_production=True,
                api_base_url=args.events_origin.rstrip("/"),
                event_api_base_url=args.events_origin.rstrip("/"),
                event_key=event_key,
                signing_key=signing,
                request_timeout=2,
            )

            def send(wake: Wake, reviewed: bool) -> None:
                assert client is not None
                client.send_sync(event_for(wake, reviewed=reviewed))

            publish = send
        app = create_app(
            service,
            auth,
            origin=f"http://127.0.0.1:{args.port}",
            trial_id=trial.name,
            publish=publish,
        )
        if client is not None:
            handlers = EventHandlers(service.store, auth.principal_for, auth.operators)
            inngest.fast_api.serve(
                app, client, build_functions(client, handlers), enable_unauthed_sync=False
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
            "Revenue console operation failed: "
            + type(error).__name__
            + "; inspect private configuration"
        )


if __name__ == "__main__":
    main()
