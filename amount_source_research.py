"""ABCD amount-applicability inventory; literal witnesses are not accepted meaning labels.

No candidate inputs, dataset partitions, grants, network requests or model calls are made.
Keep this control-plane research outside the complete frozen runtime inventories.
"""

import gzip
import io
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Annotated, Any, Literal

from agent_harness.contracts import Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin, sha256
from olist_support.reference_audit import ExposureIndex, text_pin
from pydantic import Field

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?"
MONEY = re.compile(
    rf"(?<![-.,])(?:(?:\$\s*|\bUSD\s+)(?P<prefix>{NUMBER})"
    rf"(?:\s*(?:dollars?|USD)\b)?|(?<!\w)(?P<suffix>{NUMBER})\s*(?:dollars?|USD)\b)"
    r"(?!\w|[.,]\d)",
    re.I,
)
NUMERIC = re.compile(rf"(?<![-\w.$,]){NUMBER}(?!\w|[.,]\d)")
REFUND_WORD = re.compile(r"\b(?:refund|money back)\b", re.I)
DEFAULT_TEXT = "If the customer does not know, the default amount is $50"
NativeSplit = Literal["train", "dev", "test"]


class MoneyWitness(Contract):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    lexeme_sha256: Sha256
    value: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class AmountResearchFrame(Contract):
    source_id: NonEmpty
    source_split: NativeSplit
    source_record_sha256: Sha256
    first_customer_index: Annotated[int, Field(ge=0)]
    first_visible_text_sha256: Sha256
    normalized_first_text_sha256: Sha256
    action_index: Annotated[int, Field(ge=0)]
    native_argument_sha256: Sha256
    native_amount: Decimal | None
    first_visible_money: tuple[MoneyWitness, ...]
    first_visible_currency_match: bool | None
    first_original_numeric_match: bool | None
    prior_customer_numeric_matches: int | None
    refund_lexeme_in_first_visible_text: bool
    source_policy_applies: bool
    equals_policy_default: bool | None
    flags: tuple[NonEmpty, ...]
    requested_role_validated: Literal[False] = False
    accepted_reference: Literal[False] = False


class AmountResearchAudit(Contract):
    version: Literal["olist-abcd-amount-source-research-v1"] = (
        "olist-abcd-amount-source-research-v1"
    )
    archive_sha256: Sha256
    ontology_sha256: Sha256
    guidelines_sha256: Sha256
    exposure_sha256: Sha256
    native_conversations: int
    frames: tuple[AmountResearchFrame, ...]
    input_convention: Literal["unchanged_delexed_first_customer_turn"] = (
        "unchanged_delexed_first_customer_turn"
    )
    new_cohort_prepared: Literal[False] = False
    new_labels_accepted: Literal[0] = 0
    provider_calls: Literal[0] = 0
    release_allowed: Literal[False] = False


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate source JSON field")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("nonfinite source JSON constant")


def _json(raw: bytes) -> Any:
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_nonfinite)


def _amount(text: object) -> Decimal | None:
    if not isinstance(text, str) or len(text) > 64:
        return None
    value = text.strip().removeprefix("$").strip()
    if re.fullmatch(NUMBER, value) is None:
        return None
    number = Decimal(value.replace(",", ""))
    return number if number < Decimal("1000000000000") else None


def money_witnesses(text: str) -> tuple[MoneyWitness, ...]:
    """Locate currency-marked lexemes only; negation and money roles remain unclassified."""
    result = []
    for match in MONEY.finditer(text):
        value = _amount(match.group("prefix") or match.group("suffix"))
        if value is not None:
            result.append(
                MoneyWitness(
                    start=match.start(),
                    end=match.end(),
                    lexeme_sha256=sha256(match.group().encode()),
                    value=value,
                )
            )
    return tuple(result)


def _numbers(text: str) -> set[Decimal]:
    return {n for m in NUMERIC.finditer(text) if (n := _amount(m.group())) is not None} | {
        m.value for m in money_witnesses(text)
    }


def _record_frames(
    record: dict[str, Any], split: NativeSplit, exposure: ExposureIndex
) -> tuple[str, list[AmountResearchFrame]]:
    identity = record["convo_id"]
    if type(identity) not in (int, str) or not str(identity).strip():
        raise ValueError("native conversation identity differs")
    source_id = str(identity)
    turns, original, scenario = record["delexed"], record["original"], record["scenario"]
    if (
        not isinstance(turns, list)
        or not isinstance(original, list)
        or not isinstance(scenario, dict)
    ):
        raise ValueError("native conversation schema differs")
    if any(not isinstance(t, dict) for t in turns):
        raise ValueError("native delexed turn schema differs")
    first = next((i for i, t in enumerate(turns) if t["speaker"] == "customer"), None)
    if first is None:
        raise ValueError("native conversation has no customer message")
    text = turns[first]["text"]
    if not isinstance(text, str) or not text or len(text) > 8192:
        raise ValueError("first customer text exceeds supported convention")
    aligned = len(turns) == len(original) and all(
        isinstance(o, list) and len(o) == 2 and isinstance(o[1], str) and o[0] == d["speaker"]
        for o, d in zip(original, turns, strict=True)
    )
    normalized = text_pin(text)
    mentions = money_witnesses(text)
    record_pin = sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode())
    policy = (scenario.get("flow"), scenario.get("subflow")) == (
        "product_defect",
        "refund_initiate",
    )
    frames = []
    for index, turn in enumerate(turns):
        target = turn["targets"]
        if not isinstance(target, list) or len(target) != 5:
            raise ValueError("native target shape differs")
        if target[2] != "offer-refund":
            continue
        args = target[3]
        amount = _amount(args[0]) if isinstance(args, list) and len(args) == 1 else None
        flags = {"native_action_is_not_a_requested_amount_label"}
        if source_id in exposure.source_ids:
            flags.add("previously_exposed_source")
        if normalized in exposure.normalized_text_sha256:
            flags.add("previously_exposed_first_text")
        if not aligned:
            flags.add("original_delexed_turn_alignment_differs")
        if turn["speaker"] != "action" or index <= first:
            flags.add("action_speaker_or_order_differs")
        if amount is None:
            flags.add("native_argument_not_one_supported_money_value")
        visible_match = None if amount is None else any(m.value == amount for m in mentions)
        if visible_match is False:
            flags.add("no_matching_currency_marked_value_in_first_input")
        if len({m.value for m in mentions}) > 1:
            flags.add("multiple_visible_money_values")
        original_match = (
            amount in _numbers(original[first][1]) if aligned and amount is not None else None
        )
        prior = (
            sum(amount in _numbers(o[1]) for o in original[:index] if o[0] == "customer")
            if aligned and amount is not None
            else None
        )
        if original_match and not visible_match:
            flags.add("original_numeric_match_does_not_establish_visible_input_match")
        if prior and not visible_match:
            flags.add("prior_customer_numeric_match_does_not_label_first_input")
        frames.append(
            AmountResearchFrame(
                source_id=source_id,
                source_split=split,
                source_record_sha256=record_pin,
                first_customer_index=first,
                first_visible_text_sha256=sha256(text.encode()),
                normalized_first_text_sha256=normalized,
                action_index=index,
                native_argument_sha256=sha256(
                    json.dumps(args, sort_keys=True, allow_nan=False).encode()
                ),
                native_amount=amount,
                first_visible_money=mentions,
                first_visible_currency_match=visible_match,
                first_original_numeric_match=original_match,
                prior_customer_numeric_matches=prior,
                refund_lexeme_in_first_visible_text=REFUND_WORD.search(text) is not None,
                source_policy_applies=policy,
                equals_policy_default=amount == Decimal(50)
                if policy and amount is not None
                else None,
                flags=tuple(sorted(flags)),
            )
        )
    return normalized, frames


def audit_amount_source(
    raw: bytes,
    expected_sha256: str,
    exposure: ExposureIndex,
    *,
    ontology_raw: bytes,
    ontology_sha256: str,
    guidelines_raw: bytes,
    guidelines_sha256: str,
) -> AmountResearchAudit:
    """Inventory source applicability without accepting labels or selecting a cohort."""
    if len(raw) > MAX_ARCHIVE or sha256(raw) != expected_sha256:
        raise ValueError("archive differs from external pin or size limit")
    if sha256(ontology_raw) != ontology_sha256 or sha256(guidelines_raw) != guidelines_sha256:
        raise ValueError("source policy artifacts differ from external pins")
    ontology, guidelines = _json(ontology_raw), _json(guidelines_raw)
    if ontology["actions"]["interaction"]["offer-refund"] != ["amount"]:
        raise ValueError("unsupported offer-refund ontology")
    actions = guidelines["Product Defect"]["subflows"]["Initiate Refund"]["actions"]
    offers = [a for a in actions if a["button"] == "Offer Refund"]
    if len(offers) != 1 or DEFAULT_TEXT not in offers[0]["subtext"]:
        raise ValueError("unsupported source amount policy")
    exposure = ExposureIndex.model_validate_json(exposure.canonical_json())
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as archive:
        expanded = archive.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise ValueError("expanded source exceeds limit")
    data = _json(expanded)
    if not isinstance(data, dict) or set(data) != {"train", "dev", "test"}:
        raise ValueError("native split inventory differs")
    frames, seen = [], set()
    text_splits: dict[str, set[str]] = defaultdict(set)
    for split in ("train", "dev", "test"):
        if not isinstance(data[split], list):
            raise ValueError("native split must contain a record list")
        for record in data[split]:
            normalized, selected = _record_frames(record, split, exposure)
            identity = str(record["convo_id"])
            if identity in seen:
                raise ValueError("duplicate native conversation identity")
            seen.add(identity)
            text_splits[normalized].add(split)
            frames.extend(selected)
    frames = [
        f.model_copy(
            update={
                "flags": tuple(
                    sorted(
                        {
                            *f.flags,
                            *(
                                ("first_text_crosses_native_splits",)
                                if len(text_splits[f.normalized_first_text_sha256]) > 1
                                else ()
                            ),
                        }
                    )
                )
            }
        )
        for f in frames
    ]
    return AmountResearchAudit(
        archive_sha256=expected_sha256,
        ontology_sha256=ontology_sha256,
        guidelines_sha256=guidelines_sha256,
        exposure_sha256=pin(exposure),
        native_conversations=len(seen),
        frames=tuple(frames),
    )


def summarize(audit: AmountResearchAudit) -> dict[str, object]:
    audit = AmountResearchAudit.model_validate_json(audit.canonical_json())
    frames = audit.frames
    return {
        "version": audit.version,
        "archive_sha256": audit.archive_sha256,
        "ontology_sha256": audit.ontology_sha256,
        "guidelines_sha256": audit.guidelines_sha256,
        "exposure_sha256": audit.exposure_sha256,
        "native_conversations": audit.native_conversations,
        "offer_refund_annotations": len(frames),
        "conversations_with_offer_refund": len({f.source_id for f in frames}),
        "annotation_counts_by_native_split": dict(Counter(f.source_split for f in frames)),
        "supported_numeric_arguments": sum(f.native_amount is not None for f in frames),
        "first_visible_currency_matches": sum(
            f.first_visible_currency_match is True for f in frames
        ),
        "first_visible_currency_and_refund_lexemes": sum(
            f.first_visible_currency_match is True and f.refund_lexeme_in_first_visible_text
            for f in frames
        ),
        "first_original_numeric_matches": sum(
            f.first_original_numeric_match is True for f in frames
        ),
        "equals_known_policy_default": sum(f.equals_policy_default is True for f in frames),
        "flag_counts": dict(sorted(Counter(flag for f in frames for flag in f.flags).items())),
        "input_convention": audit.input_convention,
        "requested_role_validated": False,
        "new_cohort_prepared": False,
        "new_labels_accepted": 0,
        "provider_calls": 0,
        "independence_authenticated": False,
        "release_allowed": False,
    }
