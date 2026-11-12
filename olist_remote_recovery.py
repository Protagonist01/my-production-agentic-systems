"""Pinned encrypted backup cycles and explicit new-directory recovery; no repository deletion."""

import argparse
import base64
import json
import os
import re
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import Sha256, sha256
from olist_support.backup import MAX_BYTES
from olist_support.policy_cases import external
from pydantic import AwareDatetime, Field, model_validator

from olist_backup_catalog import (
    BackupCatalog,
    Selection,
    bounded_read,
    new_file,
)

BUNDLE_NAME = "olist-private-bundle.json"
MAX_BUNDLE = MAX_BYTES * 3
RUN = re.compile(r"run-[a-f0-9]{32}")


def encode(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def validate_job_pin(job: "Job", expected: str) -> None:
    if sha256(job.canonical_json().encode()) != expected:
        raise ValueError("job requires its external canonical pin")


def pinned(path: Path, expected: str, maximum: int = 65536) -> bytes:
    if path.is_symlink():
        raise ValueError("private artifact symlink refused")
    raw = bounded_read(external(path), maximum)
    if sha256(raw) != expected:
        raise ValueError("private artifact differs from external pin")
    return raw


class Repository(Contract):
    executable: Path
    executable_sha256: Sha256
    repository_file: Path
    repository_id: Sha256
    password_file: Path
    credentials_file: Path | None = None
    backend: Literal["r2", "local_canary"]

    @model_validator(mode="after")
    def absolute_paths(self) -> Self:
        if not all(
            p.is_absolute()
            for p in (
                self.executable,
                self.repository_file,
                self.password_file,
                *((self.credentials_file,) if self.credentials_file is not None else ()),
            )
        ):
            raise ValueError("explicit absolute repository file paths required")
        return self


class Job(Contract):
    version: Literal["olist-encrypted-backup-job-v1"] = "olist-encrypted-backup-job-v1"
    repository: Repository
    root: Path
    trial: NonEmpty
    catalog: Path
    catalog_sha256: Sha256
    journal: Path
    interval_seconds: Annotated[int, Field(gt=0, le=86400)]
    max_cycle_seconds: Annotated[int, Field(gt=0, le=3600)]
    max_snapshot_age_seconds: Annotated[int, Field(gt=0, le=86400)]
    max_attempts: Annotated[int, Field(gt=0, le=1000)]

    @model_validator(mode="after")
    def timing(self) -> Self:
        if self.interval_seconds + self.max_cycle_seconds > self.max_snapshot_age_seconds:
            raise ValueError("cadence and cycle deadline exceed the snapshot-age objective")
        if not all(p.is_absolute() for p in (self.root, self.catalog, self.journal)):
            raise ValueError("absolute job paths required")
        catalog, journal = self.catalog.resolve(), self.journal.resolve()
        if catalog.is_relative_to(journal) or journal.is_relative_to(catalog):
            raise ValueError("catalog and attempt journal must be separate")
        return self


class Receipt(Contract):
    version: Literal["olist-encrypted-backup-receipt-v1"] = "olist-encrypted-backup-receipt-v1"
    job_sha256: Sha256
    repository_id: Sha256
    backend: Literal["r2", "local_canary"]
    snapshot_id: Sha256
    bundle_sha256: Sha256
    bundle_bytes: Annotated[int, Field(gt=0, le=MAX_BUNDLE)]
    catalog_sha256: Sha256
    selection: Selection
    completed_at: AwareDatetime
    elapsed_ns: Annotated[int, Field(ge=0)]
    exact_encrypted_copy_readback: Literal[True] = True
    actual_host_loss_recovery: Literal[False] = False
    provider_calls: Literal[0] = 0
    release_allowed: Literal[False] = False


class Restic:
    def __init__(self, repository: Repository, deadline: float):
        self.repository, self.deadline = repository, deadline
        executable = repository.executable
        raw = bounded_read(executable, 100_000_000)
        if sha256(raw) != repository.executable_sha256:
            raise ValueError("Restic executable differs from reviewed pin")
        location = bounded_read(external(repository.repository_file), 4096).decode().strip()
        password = bounded_read(external(repository.password_file), 4096)
        if len(password.strip()) < 32:
            raise ValueError("a separately retained strong repository password is required")
        if repository.backend == "r2":
            if (
                re.fullmatch(
                    r"s3:https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com/"
                    r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9](?:/[a-zA-Z0-9_/-]+)?",
                    location,
                )
                is None
                or repository.credentials_file is None
            ):
                raise ValueError("explicit private R2 repository and credentials required")
        else:
            # A local encrypted smoke test must be explicitly marked; never a remote fallback.
            if "://" in location or not Path(location).is_absolute():
                raise ValueError("local canary requires an explicit private filesystem repository")
            external(Path(location))
        self.environment = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}
        }
        if repository.credentials_file is not None:
            credentials = json.loads(bounded_read(external(repository.credentials_file), 8192))
            if set(credentials) != {
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_DEFAULT_REGION",
            }:
                raise ValueError("unexpected cloud credential keys")
            if not all(isinstance(v, str) and 0 < len(v) <= 2048 for v in credentials.values()):
                raise ValueError("invalid cloud credential shape")
            self.environment.update(credentials)

    def run(self, arguments: list[str], data: bytes | None = None) -> bytes:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("cycle deadline exhausted")
        result = subprocess.run(
            [
                str(self.repository.executable),
                "--no-cache",
                "--repository-file",
                str(self.repository.repository_file),
                "--password-file",
                str(self.repository.password_file),
                *arguments,
            ],
            input=data,
            capture_output=True,
            timeout=remaining,
            env=self.environment,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > MAX_BUNDLE:
            raise ValueError("Restic operation failed; private destination requires investigation")
        return result.stdout

    def verify_repository(self) -> None:
        value = json.loads(self.run(["cat", "config"]))
        if value["id"] != self.repository.repository_id:
            raise ValueError("Restic repository identity differs")

    def upload(self, raw: bytes, tag: str) -> str:
        self.verify_repository()
        lines = self.run(
            [
                "--json",
                "--quiet",
                "backup",
                "--stdin",
                "--stdin-filename",
                BUNDLE_NAME,
                "--host",
                "olist-backup",
                "--tag",
                tag,
            ],
            raw,
        ).splitlines()
        summaries = [json.loads(line) for line in lines if line.strip()]
        ids = [
            v["snapshot_id"]
            for v in summaries
            if v.get("message_type") == "summary" and "snapshot_id" in v
        ]
        if len(ids) != 1 or re.fullmatch(r"[a-f0-9]{8,64}", ids[0]) is None:
            raise ValueError("backup did not identify exactly one new snapshot")
        snapshots = json.loads(self.run(["--json", "snapshots", "--tag", tag]))
        if len(snapshots) != 1 or not snapshots[0]["id"].startswith(ids[0]):
            raise ValueError("new snapshot identity is ambiguous")
        identity = snapshots[0]["id"]
        if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
            raise ValueError("full snapshot identity required")
        if self.run(["dump", identity, "/" + BUNDLE_NAME]) != raw:
            raise ValueError("encrypted backup readback differs")
        return str(identity)


def bundle(catalog: BackupCatalog, selected: Selection) -> bytes:
    current = catalog.entry(catalog.directory / selected.entry, datetime.now(UTC))
    if (
        current.archive_sha256 != selected.archive_sha256
        or current.completion_sha256 != selected.completion_sha256
    ):
        raise ValueError("selected capture changed")
    files = {"catalog.json": bounded_read(catalog.directory / "catalog.json", 4096)}
    for name in ("archive.json", "complete.json"):
        files[name] = bounded_read(catalog.directory / selected.entry / name, MAX_BYTES * 2)
    raw = encode(
        {
            "version": "olist-encrypted-bundle-v1",
            "entry": selected.entry,
            "files": {name: base64.b64encode(data).decode() for name, data in files.items()},
        }
    )
    if len(raw) > MAX_BUNDLE:
        raise ValueError("encrypted payload exceeds bounded bundle size")
    return raw


def initialize_journal(job: Job, job_pin: str) -> None:
    validate_job_pin(job, job_pin)
    if job.journal.is_symlink():
        raise ValueError("new private journal required")
    destination = external(job.journal)
    destination.mkdir(mode=0o700)
    new_file(destination / "journal.json", encode({"job_sha256": job_pin}))


def attempt_paths(job: Job, job_pin: str) -> list[Path]:
    validate_job_pin(job, job_pin)
    if job.journal.is_symlink():
        raise ValueError("journal symlink refused")
    root = external(job.journal)
    if bounded_read(root / "journal.json", 4096) != encode({"job_sha256": job_pin}):
        raise ValueError("journal is bound to a different job")
    entries: list[Path] = []
    with os.scandir(root) as scan:
        for item in scan:
            if item.name in ("journal.json", ".job-lock"):
                continue
            if not RUN.fullmatch(item.name) or len(entries) >= job.max_attempts:
                raise ValueError("journal inventory/capacity differs")
            path = root / item.name
            if path.is_symlink() or not path.is_dir():
                raise ValueError("journal entry refused")
            entries.append(path)
    return entries


def read_success(path: Path, job: Job, job_pin: str) -> Receipt:
    if {p.name for p in path.iterdir()} != {"started.json", "success.json"}:
        raise ValueError("failed or incomplete cycle requires investigation")
    started = json.loads(bounded_read(path / "started.json", 4096))
    raw = bounded_read(path / "success.json", 65536)
    receipt = Receipt.model_validate_json(raw)
    if (
        raw != receipt.canonical_json().encode()
        or receipt.job_sha256 != job_pin
        or receipt.repository_id != job.repository.repository_id
        or receipt.backend != job.repository.backend
        or receipt.catalog_sha256 != job.catalog_sha256
        or set(started) != {"job_sha256", "started_at"}
        or started["job_sha256"] != job_pin
        or receipt.elapsed_ns > job.max_cycle_seconds * 1_000_000_000
        or receipt.completed_at < datetime.fromisoformat(started["started_at"])
        or not 0
        <= (receipt.completed_at - receipt.selection.snapshot_at).total_seconds()
        <= job.max_snapshot_age_seconds
    ):
        raise ValueError("saved cycle receipt differs from job")
    return receipt


def health(job: Job, job_pin: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("aware monitoring clock required")
    paths = attempt_paths(job, job_pin)
    receipts = []
    failures = 0
    for path in paths:
        try:
            receipt = read_success(path, job, job_pin)
            if receipt.completed_at > now:
                raise ValueError("monitoring clock precedes completion")
            receipts.append(receipt)
        except (ValueError, OSError, TypeError, LookupError):
            failures += 1
    latest = max(receipts, key=lambda r: r.selection.snapshot_at, default=None)
    age = (now - latest.selection.snapshot_at).total_seconds() if latest else None
    fresh = age is not None and 0 <= age <= job.max_snapshot_age_seconds
    lock = job.journal / ".job-lock"
    locked = lock.exists() or lock.is_symlink()
    return {
        "fresh_uploaded_snapshot": fresh,
        "snapshot_age_seconds": age,
        "healthy": job.repository.backend == "r2"
        and fresh
        and not (failures or locked or len(paths) >= job.max_attempts),
        "backend": job.repository.backend,
        "completed": len(receipts),
        "failed_or_incomplete": failures,
        "writer_lock_present": locked,
        "capacity_reached": len(paths) >= job.max_attempts,
        "actual_host_loss_recovery": False,
        "provider_calls": 0,
        "release_allowed": False,
    }


def capture_job(job: Job, deadline: float) -> Selection:
    if job.root.resolve() != Path(__file__).resolve().parent:
        raise ValueError("run this job from its actual application checkout")
    preflight = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; from olist_backup_catalog import frozen_checkout; "
            "frozen_checkout(Path.cwd())",
        ],
        cwd=job.root,
        capture_output=True,
        timeout=max(0.001, deadline - time.monotonic()),
        check=False,
    )
    if preflight.returncode != 0:
        raise ValueError("freeze source checkout before scheduled capture")
    result = subprocess.run(
        [
            sys.executable,
            str(job.root / "olist_backup_catalog.py"),
            "--catalog",
            str(job.catalog),
            "capture",
            "--root",
            str(job.root),
            "--trial",
            job.trial,
            "--catalog-sha256",
            job.catalog_sha256,
        ],
        capture_output=True,
        timeout=max(0.001, deadline - time.monotonic()),
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("database capture did not complete")
    return Selection.model_validate_json(result.stdout)


def cycle(job: Job, job_pin: str, *, allow_local_canary: bool = False) -> tuple[Receipt, str]:
    validate_job_pin(job, job_pin)
    if job.repository.backend == "local_canary" and not allow_local_canary:
        raise ValueError("local smoke tests require the explicit canary option")
    root = external(job.journal)
    lock = root / ".job-lock"
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    owned = os.fstat(fd)
    os.close(fd)
    try:
        previous = attempt_paths(job, job_pin)
        if len(previous) >= job.max_attempts:
            raise ValueError("prior failed/incomplete job or capacity requires investigation")
        for path in previous:
            read_success(path, job, job_pin)
        attempt = root / ("run-" + secrets.token_hex(16))
        attempt.mkdir(mode=0o700)
        new_file(
            attempt / "started.json",
            encode({"job_sha256": job_pin, "started_at": datetime.now(UTC).isoformat()}),
        )
        started = time.monotonic_ns()
        deadline = time.monotonic() + job.max_cycle_seconds
        try:
            catalog = BackupCatalog(job.catalog, job.catalog_sha256)
            client = Restic(job.repository, deadline)
            # Verify the selected encrypted repository before any new SQL snapshot work.
            client.verify_repository()
            selected = capture_job(job, deadline)
            raw = bundle(catalog, selected)
            identity = client.upload(raw, attempt.name)
            completed = datetime.now(UTC)
            if (
                time.monotonic() > deadline
                or not 0
                <= (completed - selected.snapshot_at).total_seconds()
                <= job.max_snapshot_age_seconds
            ):
                raise ValueError("cycle deadline or snapshot-age objective exceeded")
            receipt = Receipt(
                job_sha256=job_pin,
                repository_id=job.repository.repository_id,
                backend=job.repository.backend,
                snapshot_id=identity,
                bundle_sha256=sha256(raw),
                bundle_bytes=len(raw),
                catalog_sha256=job.catalog_sha256,
                selection=selected,
                completed_at=completed,
                elapsed_ns=time.monotonic_ns() - started,
            )
            receipt_raw = receipt.canonical_json().encode()
            new_file(attempt / "success.json", receipt_raw)
            return receipt, sha256(receipt_raw)
        except BaseException:
            new_file(attempt / "failed.json", encode({"code": "cycle_failed", "provider_calls": 0}))
            raise
    finally:
        current = lock.lstat()
        if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
            raise ValueError("job lock ownership changed")
        lock.unlink()


def recover(
    repository: Repository, receipt: Receipt, output: Path, *, seconds: int
) -> dict[str, Any]:
    if not 0 < seconds <= 3600:
        raise ValueError("explicit bounded recovery deadline required")
    if output.is_symlink() or external(output).exists():
        raise ValueError("new private recovery directory required")
    client = Restic(repository, time.monotonic() + seconds)
    if repository.repository_id != receipt.repository_id or repository.backend != receipt.backend:
        raise ValueError("recovery repository differs from saved receipt")
    client.verify_repository()
    raw = client.run(["dump", receipt.snapshot_id, "/" + BUNDLE_NAME])
    if len(raw) != receipt.bundle_bytes or sha256(raw) != receipt.bundle_sha256:
        raise ValueError("recovered encrypted bundle differs from independent receipt")
    value = json.loads(raw)
    if (
        set(value) != {"version", "entry", "files"}
        or value["version"] != "olist-encrypted-bundle-v1"
        or value["entry"] != receipt.selection.entry
    ):
        raise ValueError("recovery bundle shape differs")
    if set(value["files"]) != {"catalog.json", "archive.json", "complete.json"}:
        raise ValueError("recovery file inventory differs")
    decoded = {k: base64.b64decode(v, validate=True) for k, v in value["files"].items()}
    if any(
        len(raw) > (MAX_BYTES * 2 if name == "archive.json" else 4096)
        for name, raw in decoded.items()
    ):
        raise ValueError("recovered file size differs")
    if sha256(decoded["catalog.json"]) != receipt.catalog_sha256:
        raise ValueError("recovered catalog differs")
    if output.is_symlink():
        raise ValueError("new private recovery directory required")
    output = external(output)
    output.mkdir(mode=0o700)
    new_file(output / "catalog.json", decoded["catalog.json"])
    destination = output / receipt.selection.entry
    destination.mkdir(mode=0o700)
    for name in ("archive.json", "complete.json"):
        new_file(destination / name, decoded[name])
    selected = BackupCatalog(output, receipt.catalog_sha256).entry(destination, datetime.now(UTC))
    if (
        selected.archive_sha256 != receipt.selection.archive_sha256
        or selected.completion_sha256 != receipt.selection.completion_sha256
    ):
        raise ValueError("recovered archive identity differs")
    return {
        "recovered_bundle_verified": True,
        "archive_sha256": selected.archive_sha256,
        "entry": selected.entry,
        "database_restored": False,
        "actual_host_loss_recovery": False,
        "provider_calls": 0,
        "release_allowed": False,
    }


def render_task(job: Job, config: Path, config_pin: str, username: str) -> bytes:
    validate_job_pin(job, config_pin)
    if not config.is_absolute():
        raise ValueError("absolute private configuration path required")
    if job.interval_seconds < 60:
        raise ValueError("Windows repetition interval must be at least one minute")
    if job.repository.backend != "r2" or not username.strip() or len(username) > 128:
        raise ValueError("native schedule requires the real R2 job and explicit operator")
    ns = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    ET.register_namespace("", ns)

    def child(parent: ET.Element, name: str, text: str | None = None, **attrs: str) -> ET.Element:
        element = ET.SubElement(parent, "{" + ns + "}" + name, attrs)
        element.text = text
        return element

    task = ET.Element("{" + ns + "}Task", {"version": "1.4"})
    triggers = child(task, "Triggers")
    trigger = child(triggers, "TimeTrigger")
    repeat = child(trigger, "Repetition")
    child(repeat, "Interval", f"PT{job.interval_seconds}S")
    child(repeat, "StopAtDurationEnd", "false")
    child(trigger, "StartBoundary", datetime.now(UTC).isoformat())
    child(trigger, "Enabled", "true")
    principal = child(child(task, "Principals"), "Principal", id="Author")
    child(principal, "UserId", username)
    child(principal, "LogonType", "InteractiveToken")
    child(principal, "RunLevel", "LeastPrivilege")
    settings = child(task, "Settings")
    child(settings, "MultipleInstancesPolicy", "IgnoreNew")
    child(settings, "StartWhenAvailable", "true")
    child(settings, "Enabled", "false")
    child(settings, "ExecutionTimeLimit", f"PT{job.max_cycle_seconds + 30}S")
    execute = child(child(task, "Actions", Context="Author"), "Exec")
    child(execute, "Command", sys.executable)
    child(
        execute,
        "Arguments",
        subprocess.list2cmdline(
            [
                str(job.root / "olist_remote_recovery.py"),
                "run",
                "--config",
                str(config),
                "--pin",
                config_pin,
            ]
        ),
    )
    child(execute, "WorkingDirectory", str(job.root))
    # Task Scheduler receives a Unicode BSTR; an explicit UTF-8 XML declaration conflicts.
    return cast(bytes, ET.tostring(task, encoding="utf-8", xml_declaration=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("init-journal", "run", "health", "render-task", "recover")
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--pin", required=True)
    parser.add_argument("--allow-local-canary", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--operator")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-pin")
    parser.add_argument("--seconds", type=int)
    args = parser.parse_args(argv)
    try:
        raw = pinned(args.config, args.pin)
        if args.command == "recover":
            if (
                args.receipt is None
                or args.receipt_pin is None
                or args.output is None
                or args.seconds is None
            ):
                raise ValueError("saved receipt, new output and deadline required")
            receipt = Receipt.model_validate_json(pinned(args.receipt, args.receipt_pin))
            result = recover(
                Repository.model_validate_json(raw), receipt, args.output, seconds=args.seconds
            )
        else:
            job = Job.model_validate_json(raw)
            if raw != job.canonical_json().encode():
                raise ValueError("canonical externally pinned job required")
            if args.command == "init-journal":
                initialize_journal(job, args.pin)
                result = {"journal_initialized": True, "provider_calls": 0}
            elif args.command == "render-task":
                if args.output is None or args.operator is None:
                    raise ValueError("new task output and operator required")
                new_file(
                    external(args.output), render_task(job, args.config, args.pin, args.operator)
                )
                result = {"disabled_task_prepared": True, "task_registered": False}
            elif args.command == "health":
                result = health(job, args.pin)
                print(json.dumps(result, sort_keys=True))
                return 0 if result["healthy"] else 2
            else:
                receipt, pin = cycle(job, args.pin, allow_local_canary=args.allow_local_canary)
                result = {
                    "receipt_sha256": pin,
                    "snapshot_id": receipt.snapshot_id,
                    "backend": receipt.backend,
                    "encrypted_copy_readback": True,
                    "actual_host_loss_recovery": False,
                    "provider_calls": 0,
                }
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, LookupError, subprocess.SubprocessError):
        print('{"error":"encrypted_recovery_refused","provider_calls":0}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
