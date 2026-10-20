"""Private-file offline billing arithmetic and original-span mechanism entrypoint."""

import argparse
import json
import sqlite3
from pathlib import Path

from agent_harness.contracts import Contract

from revenue_integrity.billing_access import BillingGrant
from revenue_integrity.billing_contracts import BillingInput
from revenue_integrity.billing_worlds import read_world
from revenue_integrity.extraction import (
    SyntheticDocument,
    abstain,
    extract,
    parse_synthetic,
    reconcile_extracted,
)
from revenue_integrity.reconcile import reconcile
from revenue_integrity.source_contracts import ExtractionInput
from revenue_integrity.source_io import external


def reconcile_world(
    database: Path,
    case_id: str,
    grant: BillingGrant,
    document: SyntheticDocument | None = None,
) -> Contract:
    """Trusted tool boundary: require both read and reconcile authority."""
    grant.require(tenant_id=grant.tenant_id, world_id=case_id, capability="reconcile")
    value = read_world(database, case_id, grant)
    if document is None:
        return reconcile(value)
    return reconcile_extracted(value, document, parse_synthetic(document))


def _read(path: Path) -> bytes:
    with external(path).open("rb") as stream:
        content = stream.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError("input exceeds private-file limit")
    return content


def _run(argv: list[str] | None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    billing = commands.add_parser("reconcile")
    billing.add_argument("--input", type=Path, required=True)
    billing.add_argument("--synthetic-document", type=Path)
    scoped = commands.add_parser("reconcile-world")
    scoped.add_argument("--database", type=Path, required=True)
    scoped.add_argument("--case-id", required=True)
    scoped.add_argument("--grant", type=Path, required=True)
    scoped.add_argument("--synthetic-document", type=Path)
    original = commands.add_parser("extract-original")
    original.add_argument("--input", type=Path, required=True)
    for command in (billing, scoped, original):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result: Contract
    if args.command == "extract-original":
        result = extract(ExtractionInput.model_validate_json(_read(args.input)), abstain)
    elif args.command == "reconcile-world":
        document = (
            SyntheticDocument.model_validate_json(_read(args.synthetic_document))
            if args.synthetic_document is not None
            else None
        )
        result = reconcile_world(
            args.database,
            args.case_id,
            BillingGrant.model_validate_json(_read(args.grant)),
            document,
        )
    else:
        value = BillingInput.model_validate_json(_read(args.input))
        if args.synthetic_document is None:
            result = reconcile(value)
        else:
            document = SyntheticDocument.model_validate_json(_read(args.synthetic_document))
            result = reconcile_extracted(value, document, parse_synthetic(document))
    with external(args.output).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(result.model_dump_json(indent=2) + "\n")
    print(json.dumps({"written": True, "mode": args.command}))


def main(argv: list[str] | None = None) -> None:
    try:
        _run(argv)
    except (ValueError, OSError, sqlite3.Error):
        raise SystemExit(
            "Revenue input or output rejected; inspect private files locally."
        ) from None


if __name__ == "__main__":
    main()
