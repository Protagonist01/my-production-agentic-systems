"""Private, bounded same-version PA demo snapshots; restore only into a new trial.

Trusted administration only. Stop web/worker/operator processes before capture.
This is a local recovery mechanism, not encrypted/off-host disaster recovery.
"""

import base64
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from agent_harness.contracts import WireContract
from agent_harness.postgres import Server, Trial, verify_ownership
from prior_auth.contracts import Digest, digest
from prior_auth.review_auth import setup_review
from prior_auth.source_io import external
from psycopg import Connection, sql
from pydantic import Field

from prior_auth_demo_runtime import setup as setup_demo
from prior_auth_pipeline import ImportRequest
from prior_auth_store import setup as setup_intake

SCHEMAS = ("prior_auth_app", "prior_auth_intake", "prior_auth_demo")
Namespace = Literal["prior_auth_app", "prior_auth_intake", "prior_auth_demo"]
MAX_BYTES = 40_000_000


class Table(WireContract):
    schema_name: Literal["prior_auth_app", "prior_auth_intake", "prior_auth_demo"]
    name: Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_]*$")]
    data: str
    sha256: Digest
    rows: Annotated[int, Field(ge=0)]


class PrivateFile(WireContract):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*\.(json|txt)$")]
    data: str
    sha256: Digest


class Snapshot(WireContract):
    version: Literal["prior-auth-private-recovery-v1"] = "prior-auth-private-recovery-v1"
    created_at: datetime
    source_sha256: Digest
    code_revision: str
    environment_sha256: Digest
    server_build: str
    schema_sha256: Digest
    tables: tuple[Table, ...]
    payer_data: str
    payer_sha256: Digest
    bundle: tuple[PrivateFile, ...]


def inventory(c: Connection[Any]) -> tuple[tuple[str, str], ...]:
    rows = c.execute(
        "SELECT n.nspname,r.relname FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace "
        "WHERE n.nspname=ANY(%s) AND r.relkind='r' ORDER BY 1,2",
        (list(SCHEMAS),),
    ).fetchall()
    if not rows or {s for s, _ in rows} != set(SCHEMAS):
        raise ValueError("all three installed PA schemas required")
    dependencies = c.execute(
        "SELECT sn.nspname,s.relname,tn.nspname,t.relname FROM pg_constraint k "
        "JOIN pg_class s ON s.oid=k.conrelid JOIN pg_namespace sn ON sn.oid=s.relnamespace "
        "JOIN pg_class t ON t.oid=k.confrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace "
        "WHERE k.contype='f' AND sn.nspname=ANY(%s)",
        (list(SCHEMAS),),
    ).fetchall()
    pending = set(rows)
    ordered = []
    while pending:
        ready = sorted(
            r
            for r in pending
            if not any((s, t) == r and (rs, rt) not in ordered for s, t, rs, rt in dependencies)
        )
        if not ready:
            raise ValueError("cyclic or external foreign key unsupported")
        ordered.extend(ready)
        pending.difference_update(ready)
    return tuple(ordered)


def schema_pin(c: Connection[Any]) -> str:
    columns = c.execute(
        "SELECT n.nspname,r.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),"
        "a.attnotnull,pg_get_expr(d.adbin,d.adrelid),a.attgenerated,a.attidentity "
        "FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace "
        "JOIN pg_attribute a ON a.attrelid=r.oid LEFT JOIN pg_attrdef d "
        "ON d.adrelid=r.oid AND d.adnum=a.attnum WHERE n.nspname=ANY(%s) "
        "AND r.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3",
        (list(SCHEMAS),),
    ).fetchall()
    if (
        any(r[-1] or r[-2] for r in columns)
        or c.execute(
            "SELECT 1 FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace "
            "WHERE n.nspname=ANY(%s) AND r.relkind='S'",
            (list(SCHEMAS),),
        ).fetchone()
    ):
        raise ValueError("generated columns and sequences unsupported")
    constraints = c.execute(
        "SELECT n.nspname,r.relname,k.conname,pg_get_constraintdef(k.oid,true) "
        "FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid "
        "JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2,3",
        (list(SCHEMAS),),
    ).fetchall()
    indexes = c.execute(
        "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes "
        "WHERE schemaname=ANY(%s) ORDER BY 1,2,3",
        (list(SCHEMAS),),
    ).fetchall()
    routines = c.execute(
        "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid) FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) AND p.prokind='f' "
        "ORDER BY 1,2,3",
        (list(SCHEMAS),),
    ).fetchall()
    triggers = c.execute(
        "SELECT n.nspname,r.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
        "JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace "
        "WHERE n.nspname=ANY(%s) AND NOT t.tgisinternal ORDER BY 1,2,3",
        (list(SCHEMAS),),
    ).fetchall()
    return digest(json.dumps([inventory(c), columns, constraints, indexes, routines, triggers]))


def tables(c: Connection[Any]) -> tuple[Table, ...]:
    result = []
    size = 0
    for namespace, name in inventory(c):
        data = bytearray()
        with c.cursor().copy(
            sql.SQL(
                "COPY (SELECT * FROM {} t ORDER BY to_jsonb(t)::text) TO STDOUT (FORMAT BINARY)"
            ).format(sql.Identifier(namespace, name))
        ) as stream:
            for block in stream:
                size += len(block)
                if size > MAX_BYTES:
                    raise ValueError("snapshot size limit")
                data.extend(block)
        count = c.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(namespace, name))
        ).fetchone()
        assert count is not None
        result.append(
            Table(
                schema_name=cast(Namespace, namespace),
                name=name,
                data=base64.b64encode(data).decode(),
                sha256=hashlib.sha256(data).hexdigest(),
                rows=count[0],
            )
        )
    return tuple(result)


def payer_bytes(path: Path) -> bytes:
    path = external(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("bounded existing payer journal required")
    with tempfile.TemporaryDirectory(prefix="pa-recovery-") as temp:
        target = Path(temp) / "payer.sqlite"
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(target)) as destination:
                source.backup(destination)
        raw = target.read_bytes()
    validate_payer(raw)
    return raw


def validate_payer(raw: bytes) -> None:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("payer snapshot size limit")
    with tempfile.TemporaryDirectory(prefix="pa-journal-check-") as temp:
        path = Path(temp) / "journal.sqlite"
        path.write_bytes(raw)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as c:
            c.execute("PRAGMA trusted_schema=OFF")
            if c.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("payer journal integrity differs")
            names = c.execute(
                "SELECT type,name FROM sqlite_master WHERE type IN ('table','view','trigger')"
            ).fetchall()
            if {name for kind, name in names if kind == "table"} != {
                "pas_attempts",
                "pas_desk_packets",
                "pas_desk_inquiries",
            } or any(kind != "table" for kind, _ in names):
                raise ValueError("complete desk journal required")


def capture(
    server: Server,
    trial: Trial,
    journal: Path,
    *,
    code_revision: str,
    environment_sha256: str,
    quiescent: bool,
    bundle: Path,
) -> Snapshot:
    if not quiescent:
        raise ValueError("stop all demo processes and confirm quiescence first")
    bundle = external(bundle)
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    allowed = {
        "scope.json",
        "request.json",
        "policy.json",
        "source.txt",
        "supplement.txt",
        "supplement-request.json",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) - allowed
        or not {"scope.json", "request.json", "policy.json", "source.txt"} <= set(manifest)
    ):
        raise ValueError("complete demo bundle required")
    copies = []
    for name in sorted(set(manifest) | {"manifest.json"}):
        path = bundle / name
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            raise ValueError("bounded regular bundle file required")
        data = path.read_bytes()
        pin = hashlib.sha256(data).hexdigest()
        if name != "manifest.json" and pin != manifest[name]:
            raise ValueError("private bundle differs from manifest")
        copies.append(PrivateFile(name=name, data=base64.b64encode(data).decode(), sha256=pin))
    with server.connect() as admin:
        verify_ownership(admin, trial)
    with server.connect(trial.name) as c, c.transaction():
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        c.execute("SET LOCAL lock_timeout=2000")
        c.execute("SET LOCAL statement_timeout=15000")
        c.execute("SET LOCAL TIME ZONE 'UTC'")
        for namespace, name in inventory(c):
            c.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE NOWAIT").format(
                    sql.Identifier(namespace, name)
                )
            )
        imported = ImportRequest.model_validate_json((bundle / "request.json").read_bytes())
        if (
            hashlib.sha256((bundle / "source.txt").read_bytes()).hexdigest()
            != imported.source_sha256
        ):
            raise ValueError("bundle source binding differs")
        bound = c.execute(
            "SELECT binding_sha256 FROM prior_auth_intake.bindings "
            "WHERE tenant_id=%s AND case_id=%s",
            (imported.case.tenant_id, imported.case.case_id),
        ).fetchone()
        if not bound or bound[0] != digest(imported.case.canonical_json()):
            raise ValueError("bundle belongs to another case")
        raw = payer_bytes(journal)
        build = c.execute("SELECT version()").fetchone()
        assert build is not None
        return Snapshot(
            created_at=datetime.now(UTC),
            source_sha256=digest(trial.marker),
            code_revision=code_revision,
            environment_sha256=environment_sha256,
            server_build=build[0],
            schema_sha256=schema_pin(c),
            tables=tables(c),
            payer_data=base64.b64encode(raw).decode(),
            payer_sha256=hashlib.sha256(raw).hexdigest(),
            bundle=tuple(copies),
        )


def save(path: Path, snapshot: Snapshot) -> str:
    raw = Snapshot.model_validate_json(snapshot.canonical_json()).canonical_json().encode()
    if len(raw) > MAX_BYTES * 3:
        raise ValueError("archive size limit")
    path = external(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return hashlib.sha256(raw).hexdigest()


def read(path: Path, expected_sha256: str) -> Snapshot:
    path = external(path)
    with path.open("rb") as f:
        raw = f.read(MAX_BYTES * 3 + 1)
    if len(raw) > MAX_BYTES * 3 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("snapshot differs from external pin/limit")
    value = Snapshot.model_validate_json(raw)
    if value.canonical_json().encode() != raw:
        raise ValueError("canonical snapshot required")
    return value


def restore(
    server: Server,
    target: Trial,
    snapshot: Snapshot,
    *,
    expected_sha256: str,
    journal: Path,
    bundle_directory: Path,
) -> dict[str, object]:
    """Target must already be a new, owned, empty PA trial; never erase existing cases."""
    snapshot = Snapshot.model_validate_json(snapshot.canonical_json())
    if (
        digest(snapshot.canonical_json()) != expected_sha256
        or digest(target.marker) == snapshot.source_sha256
    ):
        raise ValueError("pinned snapshot and different target identity required")
    journal = external(journal)
    bundle_directory = external(bundle_directory)
    if bundle_directory.exists():
        raise FileExistsError("new bundle directory required")
    if journal.exists():
        raise FileExistsError("new journal required")
    raw = base64.b64decode(snapshot.payer_data, validate=True)
    if hashlib.sha256(raw).hexdigest() != snapshot.payer_sha256:
        raise ValueError("payer bytes differ")
    validate_payer(raw)
    files = []
    if not snapshot.bundle or len({f.name for f in snapshot.bundle}) != len(snapshot.bundle):
        raise ValueError("unique private bundle required")
    for f in snapshot.bundle:
        decoded = base64.b64decode(f.data, validate=True)
        if len(decoded) > 2_000_000 or hashlib.sha256(decoded).hexdigest() != f.sha256:
            raise ValueError("bundle file differs")
        files.append((f.name, decoded))
    data = []
    for table in snapshot.tables:
        block = base64.b64decode(table.data, validate=True)
        if hashlib.sha256(block).hexdigest() != table.sha256:
            raise ValueError("table bytes differ")
        data.append(block)
    if sum(map(len, data)) > MAX_BYTES:
        raise ValueError("table size limit")
    with server.connect() as admin:
        verify_ownership(admin, target)
    with server.connect(target.name) as c, c.transaction():
        # No PA schema may exist before restore. A retry requires explicit inspection.
        if c.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname=ANY(%s)", (list(SCHEMAS),)
        ).fetchone():
            raise ValueError("new empty target required")
        setup_review(c, target.name)
        setup_intake(c, target.name)
        setup_demo(c, target.name)
        c.execute("SET LOCAL TIME ZONE 'UTC'")
        build = c.execute("SELECT version()").fetchone()
        if (
            not build
            or build[0] != snapshot.server_build
            or schema_pin(c) != snapshot.schema_sha256
            or inventory(c) != tuple((t.schema_name, t.name) for t in snapshot.tables)
        ):
            raise ValueError("schema/build/inventory differs")
        names = sql.SQL(",").join(sql.Identifier(t.schema_name, t.name) for t in snapshot.tables)
        c.execute(sql.SQL("TRUNCATE {} RESTRICT").format(names))
        for table, block in zip(snapshot.tables, data, strict=True):
            with c.cursor().copy(
                sql.SQL("COPY {} FROM STDIN (FORMAT BINARY)").format(
                    sql.Identifier(table.schema_name, table.name)
                )
            ) as stream:
                stream.write(block)
        if tables(c) != snapshot.tables:
            raise ValueError("restored rows differ")
        sessions = c.execute("SELECT count(*) FROM prior_auth_app.sessions").fetchone()
        c.execute("DELETE FROM prior_auth_app.sessions")
        # Publish journal before the SQL commit; a commit failure leaves a visible
        # private partial target. Never silently clean up or run it as restored.
        with os.fdopen(
            os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as journal_file:
            journal_file.write(raw)
            journal_file.flush()
            os.fsync(journal_file.fileno())
        bundle_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, decoded in files:
            with os.fdopen(
                os.open(bundle_directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as file:
                file.write(decoded)
                file.flush()
                os.fsync(file.fileno())
    return {
        "restored": True,
        "tables": len(data),
        "sessions_revoked": sessions[0] if sessions else 0,
        "provider_calls": 0,
        "clinical_validation": False,
        "off_host_recovery": False,
    }


def main() -> None:
    import subprocess

    import psycopg
    from agent_harness.local_services import Workspace

    from prior_auth_operator import OperatorParser

    parser = OperatorParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--trial", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--journal", type=Path, required=True)
    backup.add_argument("--bundle", type=Path, required=True)
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--quiescent", action="store_true", required=True)
    recovered = commands.add_parser("restore")
    recovered.add_argument("--snapshot", type=Path, required=True)
    recovered.add_argument("--snapshot-sha256", required=True)
    recovered.add_argument("--new-journal", type=Path, required=True)
    recovered.add_argument("--new-bundle", type=Path, required=True)
    args = parser.parse_args()
    try:
        workspace = Workspace(args.root.resolve())
        server = workspace.server()
        if args.command == "backup":
            if subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=args.root, text=True
            ).strip():
                raise ValueError("clean tested checkout required")
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=args.root, text=True
            ).strip()
            snapshot = capture(
                server,
                workspace.load_trial(args.trial),
                args.journal,
                code_revision=revision,
                environment_sha256=hashlib.sha256((args.root / "uv.lock").read_bytes()).hexdigest(),
                quiescent=args.quiescent,
                bundle=args.bundle,
            )
            pin = save(args.output, snapshot)
            print(
                json.dumps(
                    {
                        "captured": True,
                        "snapshot_digest": pin,
                        "tables": len(snapshot.tables),
                        "off_host_recovery": False,
                    }
                )
            )
        else:
            snapshot = read(args.snapshot, args.snapshot_sha256)
            if (
                snapshot.environment_sha256
                != hashlib.sha256((args.root / "uv.lock").read_bytes()).hexdigest()
            ):
                raise ValueError("restore requires same dependency lock")
            trial = workspace.create(args.trial)
            print(
                json.dumps(
                    restore(
                        server,
                        trial,
                        snapshot,
                        expected_sha256=args.snapshot_sha256,
                        journal=args.new_journal,
                        bundle_directory=args.new_bundle,
                    )
                )
            )
    except (
        ValueError,
        OSError,
        LookupError,
        sqlite3.Error,
        psycopg.Error,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(
            2, type(error).__name__ + "; recovery refused; inspect private source/target state\n"
        )


if __name__ == "__main__":
    main()
