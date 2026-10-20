"""Invented contract text only; no source contracts or publisher spans are fixtures."""

import json
import sqlite3
import zipfile

import pytest
from revenue_integrity.source import import_corpus, read_inputs, read_targets, verify_corpus
from revenue_integrity.source_cli import main
from revenue_integrity.source_contracts import SourcePin
from revenue_integrity.source_io import canonical, external, load_pin, pinned_member, sha256


def words(prefix):
    return " ".join(prefix + chr(97 + i // 26) + chr(97 + i % 26) for i in range(260))


def corpus():
    contexts = [words("alpha"), words("beta"), words("beta"), words("gamma")]
    titles = [
        "issuer-a_20200101_original",
        "issuer-a_20200102_amendment",
        "issuer-b_20200103_other",
        "issuer-c_20200104_other",
    ]
    documents = []
    for i, (title, context) in enumerate(zip(titles, contexts, strict=True)):
        documents.append(
            {
                "title": title,
                "paragraphs": [
                    {
                        "context": context,
                        "qas": [
                            {
                                "id": f"invented-{i}__Document Name",
                                "question": "What is the document name?",
                                "answers": [{"answer_start": 0, "text": context.split()[0]}],
                                "is_impossible": False,
                            },
                            {
                                "id": f"invented-{i}__Renewal Term",
                                "question": "What is the renewal term?",
                                "answers": [],
                                "is_impossible": True,
                            },
                        ],
                    }
                ],
            }
        )
    return {"version": "invented-v1", "data": documents}


def fixture(tmp_path, value=None):
    raw = canonical(value if value is not None else corpus())
    archive = tmp_path / "invented.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as source:
        source.writestr("CUADv1.json", raw)
    pin = SourcePin(
        source_url="https://example.invalid/invented.zip",
        source_commit="a" * 40,
        archive_sha256=sha256(archive.read_bytes()),
        archive_bytes=archive.stat().st_size,
        member="CUADv1.json",
        member_sha256=sha256(raw),
        member_bytes=len(raw),
        contract_count=4,
        category_count=2,
    )
    return archive, pin


def test_original_context_labels_and_family_union_stay_separate(tmp_path):
    archive, pin = fixture(tmp_path)
    output = tmp_path / "prepared"
    report = import_corpus(archive, pin, output)
    assert report["counts"]["contracts"] == 4
    assert report["counts"]["questions"] == 8
    assert report["counts"]["answer_spans"] == 4
    assert report["grouping"] == {
        "issuer_edges": 1,
        "unknown_issuer_contracts": 0,
        "exact_context_edges": 1,
        "template_edges": 1,
        "family_count": 2,
        "multi_contract_families": 1,
        "largest_family": 3,
    }
    public = list(read_inputs(output / "inputs.sqlite"))
    targets = list(read_targets(output / "evaluator.sqlite"))
    assert len(public) == len(targets) == 8
    assert {item.case_id for item in public} == {item.case_id for item in targets}
    assert all(
        set(item.model_dump()) == {"schema_version", "case_id", "context", "question"}
        for item in public
    )
    assert all(item.label_authority == "CUAD-published-expert-annotations" for item in targets)
    by_family = {}
    for item in targets:
        by_family.setdefault(item.family_id, set()).add(item.split)
    assert all(len(splits) == 1 for splits in by_family.values())
    with sqlite3.connect(output / "inputs.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM contracts").fetchone() == (4,)
        assert {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        } == {"contracts", "questions"}
    verified = verify_corpus(archive, output, sha256((output / "manifest.json").read_bytes()))
    assert verified["verified"] and verified["answer_spans"] == 4
    with pytest.raises(FileExistsError):
        import_corpus(archive, pin, output)


def test_numeric_edits_cannot_cross_detected_template_boundary(tmp_path):
    value = corpus()
    value["data"][3]["paragraphs"][0]["context"] = words("alpha") + " 999.00"
    value["data"][3]["paragraphs"][0]["qas"][0]["answers"][0]["text"] = "alphaaa"
    archive, pin = fixture(tmp_path, value)
    report = import_corpus(archive, pin, tmp_path / "prepared")
    assert report["grouping"]["family_count"] == 1
    assert report["grouping"]["largest_family"] == 4


def test_unknown_issuer_is_reported_without_guessing_a_title_boundary(tmp_path):
    value = corpus()
    value["data"][3]["title"] = "invented undelimited contract"
    archive, pin = fixture(tmp_path, value)
    report = import_corpus(archive, pin, tmp_path / "prepared")
    assert report["grouping"]["unknown_issuer_contracts"] == 1
    assert report["grouping"]["family_count"] == 2


def test_original_unicode_context_uses_character_not_utf8_byte_offsets(tmp_path):
    value = corpus()
    paragraph = value["data"][0]["paragraphs"][0]
    paragraph["context"] = "é Ω " + paragraph["context"]
    paragraph["qas"][0]["answers"][0]["answer_start"] = 4
    archive, pin = fixture(tmp_path, value)
    output = tmp_path / "prepared"
    import_corpus(archive, pin, output)
    actual = next(
        item
        for item in read_inputs(output / "inputs.sqlite")
        if item.context.startswith("é") and item.question == "What is the document name?"
    )
    target = next(
        item for item in read_targets(output / "evaluator.sqlite") if item.case_id == actual.case_id
    )
    assert target.answers[0].start == 4
    assert verify_corpus(archive, output, sha256((output / "manifest.json").read_bytes()))[
        "verified"
    ]


@pytest.mark.parametrize("mutation", ["offset", "answerability", "duplicate", "category", "title"])
def test_invalid_source_is_rejected_before_output_creation(tmp_path, mutation):
    value = corpus()
    q = value["data"][0]["paragraphs"][0]["qas"][0]
    if mutation == "offset":
        q["answers"][0]["answer_start"] = 1
    elif mutation == "answerability":
        q["is_impossible"] = True
    elif mutation == "duplicate":
        q["id"] = value["data"][1]["paragraphs"][0]["qas"][0]["id"]
    elif mutation == "category":
        q["id"] = "invented-other__Absent Category"
    else:
        value["data"][0]["title"] = value["data"][1]["title"]
    archive, pin = fixture(tmp_path, value)
    with pytest.raises(ValueError):
        import_corpus(archive, pin, tmp_path / "prepared")
    assert not (tmp_path / "prepared").exists()


def test_raw_manifest_and_archive_pins_are_independent(tmp_path):
    archive, pin = fixture(tmp_path)
    manifest = tmp_path / "pin.json"
    manifest.write_bytes(canonical(pin.model_dump(mode="json")))
    assert load_pin(manifest, sha256(manifest.read_bytes())) == pin
    with pytest.raises(ValueError, match="independently supplied"):
        load_pin(manifest, "0" * 64)
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="archive size"):
        pinned_member(archive, pin)


@pytest.mark.parametrize("unsafe", ["../escape", "duplicate"])
def test_archive_inventory_is_not_extracted_or_trusted(tmp_path, unsafe):
    archive, pin = fixture(tmp_path)
    with zipfile.ZipFile(archive, "a") as source:
        if unsafe == "duplicate":
            with pytest.warns(UserWarning):
                source.writestr("CUADv1.json", b"{}")
        else:
            source.writestr(unsafe, b"payload")
    pin = pin.model_copy(
        update={
            "archive_sha256": sha256(archive.read_bytes()),
            "archive_bytes": archive.stat().st_size,
        }
    )
    with pytest.raises(ValueError):
        pinned_member(archive, pin)
    assert not (tmp_path / "escape").exists()


def test_stores_are_pinned_and_verifier_rechecks_original_labels(tmp_path):
    archive, pin = fixture(tmp_path)
    output = tmp_path / "prepared"
    report = import_corpus(archive, pin, output)
    with sqlite3.connect(output / "evaluator.sqlite") as db:
        case, raw = db.execute("SELECT case_id,target FROM targets LIMIT 1").fetchone()
        value = json.loads(raw)
        value["family_id"] = "0" * 64
        db.execute("UPDATE targets SET target=? WHERE case_id=?", (json.dumps(value), case))
    manifest = output / "manifest.json"
    with pytest.raises(ValueError, match="prepared store"):
        verify_corpus(archive, output, sha256(manifest.read_bytes()))
    report["evaluator_sha256"] = sha256((output / "evaluator.sqlite").read_bytes())
    manifest.write_bytes(canonical(report))
    with pytest.raises(ValueError, match="original source"):
        verify_corpus(archive, output, sha256(manifest.read_bytes()))


def test_verifier_recomputes_aggregate_counts_even_with_a_new_manifest_pin(tmp_path):
    archive, pin = fixture(tmp_path)
    output = tmp_path / "prepared"
    report = import_corpus(archive, pin, output)
    report["counts"]["answer_spans"] = 999
    manifest = output / "manifest.json"
    manifest.write_bytes(canonical(report))
    with pytest.raises(ValueError, match="reported source coverage"):
        verify_corpus(archive, output, sha256(manifest.read_bytes()))


@pytest.mark.parametrize("extra", ["view", "trigger", "index"])
def test_verifier_rejects_hidden_agent_schema_objects_even_after_repin(tmp_path, extra):
    archive, pin = fixture(tmp_path)
    output = tmp_path / "prepared"
    report = import_corpus(archive, pin, output)
    statements = {
        "view": "CREATE VIEW leaked_targets AS SELECT 'invented gold' AS answer",
        "trigger": "CREATE TRIGGER hidden_gold AFTER INSERT ON questions "
        "BEGIN SELECT 'invented gold'; END",
        "index": "CREATE INDEX unexpected_index ON questions(question)",
    }
    with sqlite3.connect(output / "inputs.sqlite") as db:
        db.execute(statements[extra])
    report["inputs_sha256"] = sha256((output / "inputs.sqlite").read_bytes())
    manifest = output / "manifest.json"
    manifest.write_bytes(canonical(report))
    with pytest.raises(ValueError, match="unexpected schema"):
        verify_corpus(archive, output, sha256(manifest.read_bytes()))


def test_private_paths_and_cli_errors_never_publish_source_text(tmp_path, capsys):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").write_text("gitdir: invented")
    with pytest.raises(ValueError, match="outside Git"):
        external(checkout / "private.sqlite")
    archive, pin = fixture(tmp_path)
    manifest = tmp_path / "pin.json"
    manifest.write_bytes(canonical(pin.model_dump(mode="json")))
    assert (
        main(
            [
                "prepare",
                "--archive",
                str(archive),
                "--source-manifest",
                str(manifest),
                "--source-manifest-sha256",
                "0" * 64,
                "--output",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    captured = capsys.readouterr().out
    assert "source preparation or verification failed" in captured
    assert "alphaaa" not in captured
