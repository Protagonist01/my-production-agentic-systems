"""Pinned private Olist experiment: explicit live opt-in, isolated SIM state, no release grant."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import agent_harness
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.contracts import Budget, ModelMessage, ModelRequest, RunContext
from agent_harness.controls import BoundedGateway, ExecutionPolicy, SharedControls
from agent_harness.fresh_recording import ReceiptGateway
from agent_harness.local_services import Workspace
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import CandidateSpec, verify_sources
from pydantic import TypeAdapter

import olist_support
from olist_support.business import sha
from olist_support.business_contracts import CallerGrant, RefundCommand
from olist_support.fresh_execution import execute_trial
from olist_support.fresh_release import (
    MODES,
    ExperimentPlan,
    FreshRow,
    RulesPlanner,
    TextInput,
    experiment_report,
    validate_population,
)
from olist_support.policy import POLICY_VERSION
from olist_support.policy_cases import PolicyCases, digest, external, local_clock
from olist_support.release import ScheduledTrial
from olist_support.views import OrderScope, OrderStore
from olist_support.workflow import FixedPlanner, GatewayPlanner, IntentPlan, Planner


def file_sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_private(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)


def route_template() -> ModelRequest:
    return ModelRequest(
        provider="google-gemini-developer-api",
        endpoint="https://generativelanguage.googleapis.com",
        model="gemini-3.5-flash-lite",
        messages=(
            ModelMessage(role="user", content="unused template; GatewayPlanner replaces it"),
        ),
        parameters={"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"},
    )


def verify_runtime(root: Path, candidate: CandidateSpec) -> None:
    verify_sources(root, candidate)
    for prefix, package in (
        ("harness/src/agent_harness", agent_harness),
        ("projects/olist-support/src/olist_support", olist_support),
    ):
        runtime = Path(str(package.__file__)).parent
        for path in runtime.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".sql"):
                continue
            name = prefix + "/" + path.relative_to(runtime).as_posix()
            if candidate.source_files.get(name) != file_sha(path):
                raise ValueError("executing package differs from pinned source")


def inputs_at(path: Path) -> tuple[TextInput, ...]:
    return TypeAdapter(tuple[TextInput, ...]).validate_json(external(path).read_bytes())


def make_plan(root: Path, cases: PolicyCases, inputs: tuple[TextInput, ...]) -> ExperimentPlan:
    root = root.resolve(strict=True)
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("freeze an experiment only from clean committed source")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    files = {"uv.lock": file_sha(root / "uv.lock")}
    for prefix in ("harness/src/agent_harness", "projects/olist-support/src/olist_support"):
        for path in (root / prefix).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".sql"):
                files[path.relative_to(root).as_posix()] = file_sha(path)
    config = route_template()
    spec = CandidateSpec(
        candidate="olist-gateway-intent-v1",
        code_revision=revision,
        environment_lock=files["uv.lock"],
        source_files=files,
        prompt_sha256=files["projects/olist-support/src/olist_support/workflow.py"],
        model_config_sha256=digest(config.canonical_json()),
        tools_sha256=digest("no_model_business_tools;trusted_scoped_policy_and_store_v1"),
        policy_sha256=files["projects/olist-support/src/olist_support/policy.py"],
        scorer_sha256=files["projects/olist-support/src/olist_support/release.py"],
        environment_sha256=digest(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "platform": platform.system(),
                    "lock": files["uv.lock"],
                },
                sort_keys=True,
            )
        ),
        execution=ExecutionPolicy(max_attempts=1),
        recording_budget=Budget(
            max_model_calls=36,
            max_tokens=36 * GEMINI_TOKEN_CEILING,
            max_cost=Decimal(0),
            cost_currency="USD",
        ),
    )
    tasks: list[ScheduledTrial] = []
    batch = uuid4().hex
    trials = ("trial-1", "trial-2", "trial-3")
    for case in cases.entries:
        for trial in trials:
            run = "o8-" + batch + "-" + str(len(tasks) + 1)
            view = case.input.order
            command = (
                RefundCommand(
                    tenant_id=view.tenant_id,
                    order_id=view.order_id,
                    business_operation_id=sha("olist-full-refund-v1|" + run),
                    amount_minor=case.expected.amount_minor,
                    expected_version=0,
                )
                if case.expected.amount_minor is not None
                else None
            )
            tasks.append(
                ScheduledTrial(
                    case_id=case.input.case_id,
                    trial_id=trial,
                    run_id=run,
                    grant=CallerGrant(
                        tenant_id=view.tenant_id,
                        actor_id="o8-controlled-experiment",
                        order_ids=(view.order_id,),
                        capabilities=("read", "refund"),
                    ),
                    command=command,
                    run_limit_minor=10000,
                )
            )
    canonical = "\n".join(r.canonical_json() for r in sorted(inputs, key=lambda r: r.case_id))
    result = ExperimentPlan(
        cases_sha256=digest(cases.canonical_json()),
        inputs_sha256=digest(canonical),
        candidate=spec,
        trial_ids=trials,
        tasks=tuple(tasks),
    )
    validate_population(result, cases, inputs)
    verify_runtime(root, spec)
    return result


def verify_original_source(database: Path, cases: PolicyCases) -> None:
    with closing(
        OrderStore(external(database), expected_sha256=cases.source_database_sha256)
    ) as source:
        for entry in cases.entries:
            current = entry.input.order
            original = source.view(
                OrderScope(current.tenant_id, frozenset((current.order_id,))),
                tenant_id=current.tenant_id,
                order_id=current.order_id,
                as_of=local_clock(current.as_of_source_local),
            )
            if digest(original.canonical_json()) != entry.original_view_sha256:
                raise ValueError("original view differs from pinned source")
            allowed = {
                f.removeprefix("order.") for f in entry.constructed_fields if f.startswith("order.")
            }
            a, b = original.model_dump(), current.model_dump()
            if any(a[k] != b[k] for k in a if k not in allowed):
                raise ValueError("undeclared original source edit")


def context_for(plan: ExperimentPlan, task: ScheduledTrial, cases: PolicyCases) -> RunContext:
    now = datetime.now(UTC)
    c = example_context(plan.candidate.code_revision, plan.candidate.environment_lock)
    return c.model_copy(
        update={
            "run_id": task.run_id,
            "tenant_id": task.grant.tenant_id,
            "agent_id": plan.candidate.candidate,
            "case_id": task.case_id,
            "trial_id": task.trial_id,
            "business_event_id": task.run_id,
            "mode": "fresh_candidate",
            "clock": now,
            "deadline": now + timedelta(seconds=90),
            "budget": c.budget.model_copy(
                update={"max_model_calls": 1, "max_tokens": GEMINI_TOKEN_CEILING}
            ),
            "versions": c.versions.model_copy(
                update={
                    "candidate": plan.candidate.candidate,
                    "policy": POLICY_VERSION,
                    "data_snapshot": cases.source_manifest_sha256,
                }
            ),
        }
    )


def run_experiment(
    code: Path,
    cases: PolicyCases,
    inputs: tuple[TextInput, ...],
    plan: ExperimentPlan,
    services: Path,
    output: Path,
    *,
    live: bool,
) -> dict[str, object]:
    validate_population(plan, cases, inputs)
    verify_runtime(code, plan.candidate)
    values: dict[str, str] = {}
    if live:
        from agent_harness.integration_smoke import local_environment

        values = local_environment(code)
        if (
            not values.get("GEMINI_API_KEY")
            or values.get("GEMINI_FREE_TIER_CONFIRMED", "").lower() != "true"
        ):
            raise ValueError("explicit existing Free project configuration required")
    output = external(output)
    output.mkdir(mode=0o700)
    write_private(output / "plan.json", plan.model_dump(mode="json"))
    services = external(services)
    services.mkdir(exist_ok=True, mode=0o700)
    if not (services / "compose.yaml").exists():
        shutil.copyfile(code / "compose.yaml", services / "compose.yaml")
    workspace = Workspace(services)
    workspace.config(initialize=True)
    workspace.up()
    server = workspace.server()
    case_map = {e.input.case_id: e for e in cases.entries}
    execution = uuid4().hex
    rows: list[FreshRow] = []
    controls = SharedControls()
    try:
        for mode in MODES:
            if mode == "gemini" and not live:
                continue
            folder = output / mode
            folder.mkdir()
            for index, task in enumerate(plan.tasks):
                case = case_map[task.case_id]
                root = folder / str(index + 1)
                root.mkdir()
                receipts = root / "receipts"
                receipts.mkdir()
                context = context_for(plan, task, cases)
                planner: Planner
                if mode == "gemini":
                    from agent_harness.isolated_transport import GeminiWorker, IsolatedTransport

                    capture = ReceiptGateway(
                        IsolatedTransport(GeminiWorker(values["GEMINI_API_KEY"], True)),
                        context,
                        receipts,
                        execution,
                    )
                    gateway = BoundedGateway(
                        capture,
                        controls,
                        GeminiFreeAdmission(free_tier_confirmed=True),
                        policy=plan.candidate.execution,
                    )
                    planner = GatewayPlanner(gateway, route_template())
                elif mode == "rules":
                    planner = RulesPlanner()
                else:
                    planner = FixedPlanner(IntentPlan(intent="review"))
                trial_id = "o8-" + execution[:12] + "-" + mode + "-" + str(index + 1)
                started = time.monotonic()
                try:
                    trial = workspace.create(trial_id)
                except Exception:
                    cleanup_ok = False
                    try:
                        workspace.drop(trial_id)
                        cleanup_ok = True
                    except Exception:
                        pass  # Retain the owned trial identity for explicit operator recovery.
                    row = FreshRow(
                        case_id=task.case_id,
                        trial_id=task.trial_id,
                        mode=mode,
                        observation=None,
                        decision=None,
                        elapsed_seconds=time.monotonic() - started,
                        duplicate_delivery_unchanged=False,
                        cleanup_ok=cleanup_ok,
                        errors=("trial_bootstrap_failed",),
                    )
                else:
                    row = execute_trial(
                        server,
                        trial,
                        case,
                        task,
                        context,
                        planner,
                        mode=mode,
                        receipt_root=receipts if mode == "gemini" else None,
                    )
                write_private(root / "row.json", row.model_dump(mode="json"))
                rows.append(row)
                print(
                    json.dumps(
                        {
                            "mode": mode,
                            "completed": index + 1,
                            "required": len(plan.tasks),
                            "errors": row.errors,
                        }
                    ),
                    flush=True,
                )
        verify_runtime(code, plan.candidate)
        result = experiment_report(plan, cases, inputs, tuple(rows))
        write_private(output / "report.json", result)
        inventory = {p.relative_to(output).as_posix(): file_sha(p) for p in output.rglob("*.json")}
        write_private(
            output / "evidence.json",
            {
                "execution_id": execution,
                "origin": "provider" if live else "deterministic_only",
                "plan_sha256": digest(plan.canonical_json()),
                "files": inventory,
            },
        )
        return result
    finally:
        workspace.down()


def read_experiment(
    directory: Path,
    evidence_sha256: str,
    cases: PolicyCases,
    inputs: tuple[TextInput, ...],
) -> dict[str, object]:
    """Offline independent artifact read-back, with an externally retained evidence pin."""
    directory = external(directory)
    evidence_path = directory / "evidence.json"
    if file_sha(evidence_path) != evidence_sha256:
        raise ValueError("external evidence pin differs")
    evidence = json.loads(evidence_path.read_bytes())
    actual = {
        p.relative_to(directory).as_posix(): file_sha(p)
        for p in directory.rglob("*.json")
        if p != evidence_path
    }
    if actual != evidence["files"] or any(p.is_symlink() for p in directory.rglob("*")):
        raise ValueError("evidence inventory changed")
    plan = ExperimentPlan.model_validate_json((directory / "plan.json").read_bytes())
    if digest(plan.canonical_json()) != evidence["plan_sha256"]:
        raise ValueError("sealed plan differs")
    rows = []
    for path in sorted(directory.glob("*/*/row.json")):
        row = FreshRow.model_validate_json(path.read_bytes())
        captured = tuple(
            # The embedded exchange and its separately persisted receipt must agree.
            p.read_bytes()
            for p in sorted((path.parent / "receipts").glob("*.json"))
        )
        from agent_harness.release_contracts import AttemptReceipt

        parsed = tuple(AttemptReceipt.model_validate_json(p) for p in captured)
        if parsed != row.receipts or any(
            p.execution_id != evidence["execution_id"] for p in parsed
        ):
            raise ValueError("separately stored attempt receipt differs")
        if path.parent.parent.name != row.mode:
            raise ValueError("row is stored under another mode")
        rows.append(row)
    result = experiment_report(plan, cases, inputs, tuple(rows))
    recorded = json.loads((directory / "report.json").read_bytes())
    if json.dumps(result, sort_keys=True) != json.dumps(recorded, sort_keys=True):
        raise ValueError("stored report differs from independent recomputation")
    if evidence["origin"] != (
        "provider" if any(r.mode == "gemini" for r in rows) else "deterministic_only"
    ):
        raise ValueError("evidence origin differs from executed modes")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "report"))
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--cases-sha256", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--inputs-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-database", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--plan-pin")
    parser.add_argument("--service-root", type=Path)
    parser.add_argument("--live-gemini", action="store_true")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--evidence-sha256")
    args = parser.parse_args()
    cases_path, inputs_path = external(args.cases), external(args.inputs)
    if file_sha(cases_path) != args.cases_sha256 or file_sha(inputs_path) != args.inputs_sha256:
        raise ValueError("independently supplied input byte pins differ")
    cases = PolicyCases.model_validate_json(cases_path.read_bytes())
    inputs = inputs_at(inputs_path)
    verify_original_source(args.source_database, cases)
    if args.command == "plan":
        plan = make_plan(args.code_root, cases, inputs)
        write_private(external(args.output), plan.model_dump(mode="json"))
        print(
            json.dumps(
                {"plan_pin": digest(plan.canonical_json()), "scheduled_live_calls": len(plan.tasks)}
            )
        )
    elif args.command == "run":
        if args.plan is None or args.service_root is None or args.plan_pin is None:
            raise ValueError("run requires external pinned plan and service root")
        plan = ExperimentPlan.model_validate_json(external(args.plan).read_bytes())
        if digest(plan.canonical_json()) != args.plan_pin:
            raise ValueError("external plan pin differs")
        result = run_experiment(
            args.code_root,
            cases,
            inputs,
            plan,
            args.service_root,
            args.output,
            live=args.live_gemini,
        )
        print(
            json.dumps(
                {
                    "version": result["version"],
                    "release_allowed": False,
                    "evidence_sha256": file_sha(external(args.output) / "evidence.json"),
                }
            )
        )
    else:
        if args.evidence_root is None or args.evidence_sha256 is None:
            raise ValueError("report requires external evidence root and separately retained pin")
        result = read_experiment(args.evidence_root, args.evidence_sha256, cases, inputs)
        write_private(external(args.output), result)
        print(json.dumps({"recomputed": True, "release_allowed": False}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "O8 experiment rejected; inspect private inputs, source pins and owned service state"
        ) from None
