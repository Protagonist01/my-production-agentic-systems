"""Bounded private snapshot discovery; no deletion, scheduler, cutover or provider calls."""

import argparse
import base64
import json
import math
import os
import re
import secrets
import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Any, Literal

import psycopg
from agent_harness.contracts import Contract
from agent_harness.local_services import Workspace
from agent_harness.release_contracts import Sha256, sha256
from olist_support.backup import MAX_BYTES, SCHEMAS, Archive, capture
from olist_support.policy_cases import external
from pydantic import AwareDatetime, Field, TypeAdapter

ENTRY = re.compile(r"backup-[a-f0-9]{32}")


class Marker(Contract):
    version: Literal["olist-backup-catalog-v1"] = "olist-backup-catalog-v1"
    source_identity_sha256: Sha256
    max_entries: Annotated[int, Field(ge=1, le=1000)]


class Completion(Contract):
    version: Literal["olist-backup-complete-v1"] = "olist-backup-complete-v1"
    catalog_sha256: Sha256
    archive_sha256: Sha256
    snapshot_at: AwareDatetime
    completed_at: AwareDatetime
    tables: Annotated[int, Field(gt=0)]
    rows: Annotated[int, Field(ge=0)]


class Selection(Contract):
    entry: Annotated[str, Field(pattern=r"^backup-[a-f0-9]{32}$")]
    archive_sha256: Sha256
    completion_sha256: Sha256
    snapshot_at: AwareDatetime
    age_seconds: Annotated[float, Field(ge=0)]
    tables: Annotated[int, Field(gt=0)]
    rows: Annotated[int, Field(ge=0)]


def new_file(path: Path, raw: bytes) -> None:
    """Exclusive write; final receipt is never published before archive flush/readback."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def bounded_read(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("backup artifact refused")
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError("backup artifact exceeds limit")
    return raw


def validate_archive(raw: bytes, source_pin: str) -> Archive:
    archive = Archive.model_validate_json(raw)
    if raw != archive.canonical_json().encode() or archive.source_identity_sha256 != source_pin:
        raise ValueError("backup source/canonical bytes differ")
    inventory = [(t.namespace, t.table) for t in archive.tables]
    if len(inventory) != len(set(inventory)) or {s for s, _ in inventory} != set(SCHEMAS):
        raise ValueError("backup requires all four schemas and unique tables")
    size = 0
    for table in archive.tables:
        data = base64.b64decode(table.data_base64, validate=True)
        size += len(data)
        if size > MAX_BYTES or sha256(data) != table.data_sha256:
            raise ValueError("backup table bytes differ")
    return archive


def frozen_checkout(root: Path) -> tuple[str, str]:
    """Bind this entrypoint and editable runtime imports to the actual clean checkout."""
    if root != Path(__file__).resolve().parent or any(
        Path(str(files(package))).resolve() != root / relative
        for package, relative in (
            ("olist_support", "projects/olist-support/src/olist_support"),
            ("agent_harness", "harness/src/agent_harness"),
        )
    ):
        raise ValueError("run the locked editable workspace from its own checkout")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("freeze checkout before backup")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        raise ValueError("actual checkout revision required")
    return revision, sha256((root / "uv.lock").read_bytes())


class BackupCatalog:
    def __init__(self, directory: Path, marker_sha256: str):
        if directory.is_symlink():
            raise ValueError("catalog symlink refused")
        self.directory = external(directory)
        self.marker_sha256 = TypeAdapter(Sha256).validate_python(marker_sha256)
        raw = bounded_read(self.directory / "catalog.json", 4096)
        self.marker = Marker.model_validate_json(raw)
        if sha256(raw) != self.marker_sha256 or raw != self.marker.canonical_json().encode():
            raise ValueError("catalog differs from external marker pin")

    @classmethod
    def initialize(cls, directory: Path, marker: Marker) -> "BackupCatalog":
        if directory.is_symlink():
            raise ValueError("catalog symlink refused")
        directory = external(directory)
        raw = Marker.model_validate_json(marker.canonical_json()).canonical_json().encode()
        directory.mkdir(mode=0o700)
        new_file(directory / "catalog.json", raw)
        return cls(directory, sha256(raw))

    def paths(self) -> list[Path]:
        if sha256(bounded_read(self.directory / "catalog.json", 4096)) != self.marker_sha256:
            raise ValueError("catalog marker changed")
        entries: list[Path] = []
        with os.scandir(self.directory) as stream:
            for item in stream:
                if item.name in ("catalog.json", ".writer-lock"):
                    continue
                if not ENTRY.fullmatch(item.name) or len(entries) >= self.marker.max_entries:
                    raise ValueError("catalog inventory/capacity refused")
                entries.append(self.directory / item.name)
        return entries

    @contextmanager
    def writing(self) -> Iterator[None]:
        lock = self.directory / ".writer-lock"
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        owned = os.fstat(fd)
        os.close(fd)
        try:
            yield
        finally:
            current = lock.lstat()
            if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
                raise ValueError("writer lock ownership changed")
            lock.unlink()

    def entry(self, path: Path, now: datetime) -> Selection:
        if path.is_symlink() or not path.is_dir():
            raise ValueError("backup entry refused")
        if {p.name for p in path.iterdir()} != {"archive.json", "complete.json"}:
            raise ValueError("backup entry inventory differs")
        raw = bounded_read(path / "archive.json", MAX_BYTES * 2)
        archive = validate_archive(raw, self.marker.source_identity_sha256)
        complete_raw = bounded_read(path / "complete.json", 4096)
        complete = Completion.model_validate_json(complete_raw)
        age = (now - archive.created_at).total_seconds()
        if (
            complete_raw != complete.canonical_json().encode()
            or complete.catalog_sha256 != self.marker_sha256
            or complete.archive_sha256 != sha256(raw)
            or complete.snapshot_at != archive.created_at
            or complete.completed_at < archive.created_at
            or complete.completed_at > now
            or complete.tables != len(archive.tables)
            or complete.rows != sum(t.rows for t in archive.tables)
            or age < 0
        ):
            raise ValueError("backup completion/time differs")
        return Selection(
            entry=path.name,
            archive_sha256=complete.archive_sha256,
            completion_sha256=sha256(complete_raw),
            snapshot_at=archive.created_at,
            age_seconds=age,
            tables=complete.tables,
            rows=complete.rows,
        )

    def publish(self, producer: Callable[[], Archive]) -> Selection:
        # Take the lock before capacity checks or SQL. Preserve a failed entry for diagnosis.
        with self.writing():
            if len(self.paths()) >= self.marker.max_entries:
                raise ValueError("catalog capacity reached; nothing was deleted")
            destination = self.directory / ("backup-" + secrets.token_hex(16))
            destination.mkdir(mode=0o700)
            archive = producer()
            raw = archive.canonical_json().encode()
            if len(raw) > MAX_BYTES * 2:
                raise ValueError("backup exceeds limit")
            archive = validate_archive(raw, self.marker.source_identity_sha256)
            if archive.created_at > datetime.now(UTC):
                raise ValueError("future snapshot refused")
            new_file(destination / "archive.json", raw)
            stored = bounded_read(destination / "archive.json", MAX_BYTES * 2)
            if stored != raw:
                raise ValueError("backup readback differs")
            validate_archive(stored, self.marker.source_identity_sha256)
            complete = Completion(
                catalog_sha256=self.marker_sha256,
                archive_sha256=sha256(raw),
                snapshot_at=archive.created_at,
                completed_at=datetime.now(UTC),
                tables=len(archive.tables),
                rows=sum(t.rows for t in archive.tables),
            )
            new_file(destination / "complete.json", complete.canonical_json().encode())
            return self.entry(destination, datetime.now(UTC))

    def status(self, *, max_age_seconds: float, now: datetime | None = None) -> dict[str, Any]:
        if not math.isfinite(max_age_seconds) or not 0 < max_age_seconds <= 86400:
            raise ValueError("explicit positive bounded backup age required")
        now = TypeAdapter(AwareDatetime).validate_python(now or datetime.now(UTC))
        entries = self.paths()
        valid = []
        incomplete = invalid = 0
        for path in entries:
            if not path.is_symlink() and path.is_dir() and not (path / "complete.json").exists():
                incomplete += 1
                continue
            try:
                valid.append(self.entry(path, now))
            except (ValueError, OSError, TypeError):
                invalid += 1
        latest = max(valid, key=lambda v: (v.snapshot_at, v.entry), default=None)
        fresh = latest is not None and latest.age_seconds <= max_age_seconds
        lock = self.directory / ".writer-lock"
        locked = lock.exists() or lock.is_symlink()
        capacity = len(entries) >= self.marker.max_entries
        return {
            "version": "olist-backup-status-v1",
            "healthy": fresh and not (incomplete or invalid or locked or capacity),
            "fresh_snapshot_available": fresh,
            "latest": latest.model_dump(mode="json") if latest else None,
            "completed": len(valid),
            "incomplete": incomplete,
            "invalid": invalid,
            "writer_lock_present": locked,
            "capacity_reached": capacity,
            "max_age_seconds": max_age_seconds,
            "actual_restore_verified": False,
            "host_loss_rpo_rto_verified": False,
            "provider_calls": 0,
            "release_allowed": False,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--max-entries", type=int, required=True)
    take = commands.add_parser("capture")
    for command in (init, take):
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--trial", required=True)
    status = commands.add_parser("status")
    status.add_argument("--max-age-seconds", type=float, required=True)
    for command in (take, status):
        command.add_argument("--catalog-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            catalog = BackupCatalog(args.catalog, args.catalog_sha256)
            report = catalog.status(max_age_seconds=args.max_age_seconds)
            print(json.dumps(report, sort_keys=True))
            return 0 if report["healthy"] else 2
        workspace = Workspace(args.root.resolve())
        source = workspace.load_trial(args.trial)
        source_pin = sha256(source.marker.encode())
        if args.command == "init":
            catalog = BackupCatalog.initialize(
                args.catalog,
                Marker(source_identity_sha256=source_pin, max_entries=args.max_entries),
            )
            print(json.dumps({"catalog_sha256": catalog.marker_sha256}))
            return 0
        catalog = BackupCatalog(args.catalog, args.catalog_sha256)
        if catalog.marker.source_identity_sha256 != source_pin:
            raise ValueError("catalog source differs")

        def frozen_capture() -> Archive:
            revision, lock_pin = frozen_checkout(workspace.root)
            archive = capture(
                workspace.server(), source, code_revision=revision, environment_lock=lock_pin
            )
            if frozen_checkout(workspace.root) != (revision, lock_pin):
                raise ValueError("checkout changed during capture")
            return archive

        selected = catalog.publish(frozen_capture)
        print(selected.canonical_json())
        return 0
    except (ValueError, OSError, TypeError, psycopg.Error, subprocess.SubprocessError):
        print('{"error":"backup_operation_refused","provider_calls":0}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
