"""Private approved 12-example scope draft. No provider, gold labels or source test decoding."""

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

CLINC_INTENTS = ("weather", "recipe", "translate", "how_old_are_you")
BANK_OPERATIONS = ("cancel_transfer", "terminate_account", "change_pin", "exchange_rate")
BANK_COMPLAINTS = (
    "transaction_charged_twice",
    "extra_charge_on_statement",
    "card_payment_not_recognised",
    "compromised_card",
)


def training_member(raw):
    """Select the top-level train array without JSON/UTF-8 decoding other split values.

    The original CLINC publisher container mixes splits. Byte-level balanced scanning
    skips earlier values; stop as soon as train is decoded. No test examples are returned.
    """
    if len(raw) > 20_000_000:
        raise ValueError("source exceeds bound")
    whitespace = b" \t\r\n"

    def skip(i):
        while i < len(raw) and raw[i] in whitespace:
            i += 1
        return i

    def end(i):
        stack = []
        quoted = escaped = False
        for j in range(i, len(raw)):
            c = raw[j]
            if quoted:
                if escaped:
                    escaped = False
                elif c == 92:
                    escaped = True
                elif c == 34:
                    quoted = False
                    if not stack:
                        return j + 1
            elif c == 34:
                quoted = True
            elif c in (91, 123):
                stack.append(c)
            elif c in (93, 125):
                if not stack or (stack.pop(), c) not in ((91, 93), (123, 125)):
                    raise ValueError("source structure invalid")
                if not stack:
                    return j + 1
            elif not stack and c in (44, 32, 9, 10, 13):
                return j
        raise ValueError("source value incomplete")

    i = skip(0)
    if raw[i : i + 1] != b"{":
        raise ValueError("publisher object required")
    i = skip(i + 1)
    while raw[i : i + 1] != b"}":
        key_end = end(i)
        key = json.loads(raw[i:key_end])  # decode only top-level property names
        i = skip(key_end)
        if raw[i : i + 1] != b":":
            raise ValueError("source separator missing")
        i = skip(i + 1)
        value_end = end(i)
        if key == "train":
            value = json.loads(raw[i:value_end])
            if not isinstance(value, list):
                raise ValueError("training array required")
            return value
        i = skip(value_end)
        if raw[i : i + 1] == b",":
            i = skip(i + 1)
        elif raw[i : i + 1] != b"}":
            raise ValueError("source separator missing")
    raise ValueError("training split unavailable")


def choose(rows, intents):
    selected = []
    for label in intents:
        choices = [(text, category) for text, category in rows if category == label]
        if not choices:
            raise ValueError("requested intent missing")
        selected.append(
            min(
                choices,
                key=lambda row: hashlib.sha256(
                    json.dumps(row, ensure_ascii=False).encode()
                ).hexdigest(),
            )
        )
    return selected


def draft(clinc_train, bank_train):
    groups = (
        ("unrelated_candidate", choose(clinc_train, CLINC_INTENTS), "clinc150"),
        ("operation_or_information", choose(bank_train, BANK_OPERATIONS), "banking77"),
        ("complaint_like", choose(bank_train, BANK_COMPLAINTS), "banking77"),
    )
    rows = []
    for group, selected, source in groups:
        for text, label in selected:
            if not isinstance(text, str) or not 1 <= len(text) <= 20000:
                raise ValueError("bounded source text required")
            rows.append(
                {
                    "case_id": f"mapping-{len(rows) + 1:02d}",
                    "source": source,
                    "publisher_split": "train",
                    "publisher_label": label,
                    "original_text": text,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "selection": "lowest_sha256_of_text_label_within_predeclared_intent",
                    "selection_group": group,
                    "project_mapping_status": "unreviewed_proposal",
                    "masking_flags": [
                        name
                        for name, pattern in (
                            ("email", r"\b\S+@\S+\b"),
                            ("long_number", r"\d{6,}"),
                            ("url", r"https?://\S+"),
                        )
                        if re.search(pattern, text)
                    ],
                }
            )
    if len({r["text_sha256"] for r in rows}) != 12:
        raise ValueError("duplicate draft input")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinc-training-member", type=Path, required=True)
    parser.add_argument("--bank-training-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if any((p / ".git").exists() for p in output.parents):
        raise ValueError("private output required")
    clinc = json.loads(args.clinc_training_member.read_bytes())
    bank = [
        (r["text"], r["category"])
        for r in csv.DictReader(io.StringIO(args.bank_training_csv.read_text(encoding="utf-8-sig")))
    ]
    with output.open("x", encoding="utf-8") as target:
        json.dump(draft(clinc, bank), target, indent=2, ensure_ascii=False)
