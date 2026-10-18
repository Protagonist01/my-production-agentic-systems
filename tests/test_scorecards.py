"""H9 denominator, provenance, uncertainty and baseline regression acceptance."""

import json
from decimal import Decimal

import pytest
from agent_harness.fault_contracts import digest
from agent_harness.scorecard_compare import compare_batches
from agent_harness.scorecard_contracts import ReportPolicy, Scorecard
from agent_harness.scorecard_render import render_comparison, render_scorecard
from agent_harness.scorecard_stats import binomial_bounds
from agent_harness.scorecards import build_scorecard
from agent_harness.trials import BatchReport
from scorecard_fixtures import batch, population


def policy(repeated=()):
    return ReportPolicy(
        version="reviewed-reporting-v1", required_case_ids=("case-0",), repeated_case_ids=repeated
    )


def report(value, loaded, chosen=None, **kwargs):
    return build_scorecard(
        value, loaded, chosen or policy(), reporter_revision="invented-reporter", **kwargs
    )


def compare(old, new, loaded, **kwargs):
    return compare_batches(
        old,
        new,
        loaded,
        policy(),
        reporter_revision="invented-reporter",
        baseline_sha256=digest(old),
        **kwargs,
    )


def test_missing_errors_and_known_unsafe_cannot_improve_denominators():
    loaded, schedule = population(count=6)
    value = batch(
        loaded,
        schedule,
        {
            ("case-1", "trial-0"): "missing",
            ("case-2", "trial-0"): "worker_error",
            ("case-3", "trial-0"): "scorer_error",
            ("case-4", "trial-0"): "unsafe_error",
            ("case-5", "trial-0"): "cleanup_error",
        },
    )
    card = report(value, loaded)
    assert card.overall.autonomous_completion.numerator == 1
    assert card.overall.autonomous_completion.denominator == 6
    assert card.overall.missing_rows == 1 and card.overall.present_rows == 5
    assert card.overall.category_counts == {
        "autonomous_completion": 1,
        "missing": 1,
        "unsafe": 1,
        "unverified": 3,
    }
    assert card.overall.observed_violations.numerator == 1
    assert card.overall.observed_violations.unknown == 4
    assert len(card.cases) == 6 and sum(len(c.trials) for c in card.cases) == 6
    assert card.overall.usage.model_calls is None
    assert card.overall.usage.known_model_calls == 4
    assert card.overall.usage.unknown_model_call_trials == 4
    text = card.canonical_json() + render_scorecard(card)
    for secret in ("HIDDEN-CANARY", "PRIVATE-OUTPUT-CANARY", "PRIVATE-SCORER-CANARY"):
        assert secret not in text
    assert Scorecard.model_validate_json(card.canonical_json()) == card


def test_no_rows_is_zero_of_scheduled_not_zero_of_zero():
    loaded, schedule = population(count=2, trials=3)
    card = report(BatchReport(schedule=schedule, rows=()), loaded)
    assert (
        card.overall.autonomous_completion.numerator,
        card.overall.autonomous_completion.denominator,
    ) == (0, 6)
    assert card.overall.autonomous_completion.unknown == 6
    assert card.overall.usage.model_calls is None and card.overall.usage.unknown_cost_trials == 6
    assert card.overall.safety_uncertainty.unknown_groups == 2
    assert card.overall.safety_uncertainty.lower == 0 and card.overall.safety_uncertainty.upper == 1


def test_escalating_everything_earns_no_autonomous_credit_and_review_is_separate():
    loaded, schedule = population(count=3, review_last=True)
    card = report(
        batch(loaded, schedule, dict.fromkeys((t.key for t in schedule.tasks), "review")), loaded
    )
    assert (
        card.overall.autonomous_completion.numerator,
        card.overall.autonomous_completion.denominator,
    ) == (0, 2)
    assert card.overall.appropriate_review.numerator == 1
    assert card.overall.appropriate_review.denominator == 1
    assert card.overall.unnecessary_review.numerator == 2
    assert card.overall.unnecessary_review.denominator == 2
    assert card.overall.observed_review.numerator == 3
    assert card.overall.usage.cost_per_autonomous_completion is None


def test_required_review_completion_is_unsafe_even_with_positive_safety_score():
    loaded, schedule = population(count=1, review_last=True)
    card = report(batch(loaded, schedule), loaded)
    assert card.overall.observed_violations.numerator == 1
    assert card.overall.autonomous_completion.denominator == 0
    assert card.overall.autonomous_completion.value is None


@pytest.mark.parametrize(
    "field", ["group_id", "split", "scorer_id", "source_kind", "source_version", "scorer_version"]
)
def test_wrapped_provenance_cannot_override_reviewed_manifest(field):
    loaded, schedule = population(count=1)
    value = json.loads(batch(loaded, schedule).canonical_json())
    target = value["rows"][0]["report"]
    if field in ("source_kind", "source_version", "scorer_version"):
        target = target["report"]
    target[field] = {"split": "holdout", "source_kind": "original"}.get(field, "changed")
    if field == "scorer_version":
        for score in target["scores"]:
            score["scorer_version"] = "changed"
    with pytest.raises(ValueError, match="provenance"):
        report(BatchReport.model_validate_json(json.dumps(value)), loaded)


@pytest.mark.parametrize("mode", ["offline_fake", "strict_replay", "fresh_candidate"])
def test_modes_and_source_split_slices_are_explicit_and_missing_rows_stay_in_slice(mode):
    loaded, schedule = population(mode=mode)
    card = report(batch(loaded, schedule, {("case-2", "trial-0"): "missing"}), loaded)
    assert card.mode == mode and card.freshness_verified is False
    slices = {(s.dimension, s.label): s.summary for s in card.slices}
    assert slices["source_kind", "original"].missing_rows == 1
    assert slices["source_kind", "original"].autonomous_completion.denominator == 1
    assert slices["split", "holdout"].autonomous_completion.denominator == 2
    assert slices["tag", "shared-tag"].scheduled_trials == 3


@pytest.mark.parametrize("count", [1, 10, 100, 1000000])
def test_zero_event_exact_interval_has_positive_upper_bound(count):
    lower, upper = binomial_bounds(0, count)
    assert lower == 0 and upper == pytest.approx(1 - 0.025 ** (1 / count))
    assert upper > 0
    assert binomial_bounds(count, count) == pytest.approx((0.025 ** (1 / count), 1))


def test_binomial_counts_and_known_interior_reference():
    assert binomial_bounds(0, 0) == (None, None)
    assert binomial_bounds(4, 20) == pytest.approx((0.0806576626, 0.4160174323))
    for args in ((-1, 2), (3, 2), (0, -1)):
        with pytest.raises(ValueError):
            binomial_bounds(*args)


def test_repeated_related_cases_do_not_manufacture_independent_safety_samples():
    loaded, schedule = population(count=3, trials=3, same_group=True)
    card = report(batch(loaded, schedule), loaded)
    assert card.overall.observed_violations.denominator == 9
    assert card.overall.safety_uncertainty.groups == 1
    assert card.overall.safety_uncertainty.upper == pytest.approx(0.975)
    unknown = report(batch(loaded, schedule, {("case-1", "trial-2"): "missing"}), loaded)
    assert unknown.overall.safety_uncertainty.unknown_groups == 1
    assert unknown.overall.safety_uncertainty.upper == 1
    unsafe = report(batch(loaded, schedule, {("case-1", "trial-2"): "unsafe_error"}), loaded)
    assert unsafe.overall.safety_uncertainty.observed_event_groups == 1
    assert unsafe.overall.safety_uncertainty.unknown_groups == 0


@pytest.mark.parametrize(
    "mode,trials,status",
    [
        ("offline_fake", 3, "requires_fresh_candidate"),
        ("strict_replay", 3, "requires_fresh_candidate"),
        ("fresh_candidate", 2, "requires_exactly_three_trials"),
        ("fresh_candidate", 3, "reported"),
    ],
)
def test_all_three_correct_requires_declared_subset_and_exact_fresh_mode_population(
    mode, trials, status
):
    loaded, schedule = population(trials=trials, mode=mode)
    value = batch(loaded, schedule, {("case-0", "trial-1"): "missing"})
    repeated = report(value, loaded, policy(("case-0",))).repeated_correctness
    assert repeated.status == status and repeated.freshness_verified is False
    if status == "reported":
        assert repeated.all_three_correct.numerator == 0
        assert repeated.all_three_correct.denominator == 1
        assert repeated.all_three_correct.unknown == 1
    else:
        assert repeated.all_three_correct is None
    assert report(value, loaded).repeated_correctness.status == "not_declared"


def test_partial_unknown_usage_and_mixed_currency_never_become_full_total():
    loaded, schedule = population(count=2)
    value = json.loads(batch(loaded, schedule).canonical_json())
    value["rows"][0]["report"]["report"]["result"]["usage"]["input_tokens"] = None
    value["rows"][1]["report"]["report"]["result"]["usage"]["cost_currency"] = "EUR"
    card = report(BatchReport.model_validate_json(json.dumps(value)), loaded)
    usage = card.overall.usage
    assert usage.model_calls == 2 and usage.input_tokens is None and usage.known_input_tokens == 2
    assert (
        usage.unknown_input_token_trials == 1 and usage.cost is None and usage.cost_currency is None
    )
    assert usage.known_cost_by_currency == {"EUR": Decimal("0.01"), "USD": Decimal("0.01")}
    assert usage.cost_per_autonomous_completion is None
    complete = report(batch(loaded, schedule), loaded).overall.usage
    assert complete.cost == Decimal("0.02") and complete.cost_per_autonomous_completion == Decimal(
        "0.01"
    )


def test_improving_average_cannot_hide_a_required_case_regression_or_missing_outcome():
    loaded, schedule = population()
    old = batch(loaded, schedule, {("case-1", "trial-0"): "fail", ("case-2", "trial-0"): "fail"})
    new = batch(loaded, schedule, {("case-0", "trial-0"): "missing"})
    result = compare(old, new, loaded)
    assert result.completion_delta == pytest.approx(1 / 3)
    assert result.newly_failing_required_cases == ("case-0",)
    assert result.cases[0].regressed_trial_ids == ("trial-0",)
    assert result.cases[0].new_unverified_trial_ids == ("trial-0",)
    assert result.release_decision == "not_performed"
    assert "case\\-0" in render_comparison(result)


def test_new_unsafe_and_incomplete_results_are_visible_even_on_nonrequired_case():
    loaded, schedule = population()
    result = compare(
        batch(loaded, schedule),
        batch(loaded, schedule, {("case-1", "trial-0"): "unsafe_error"}),
        loaded,
    )
    assert result.cases[1].new_unsafe_trial_ids == ("trial-0",)
    assert result.cases[1].new_unverified_trial_ids == ("trial-0",)


@pytest.mark.parametrize(
    "change", ["mode", "seed", "clock", "budget", "environment", "policy", "keys", "digest"]
)
def test_incompatible_pairing_fails_closed(change):
    loaded, schedule = population()
    old = batch(loaded, schedule)
    data = json.loads(old.canonical_json())
    if change == "digest":
        with pytest.raises(ValueError, match="digest"):
            compare_batches(
                old, old, loaded, policy(), reporter_revision="test", baseline_sha256="0" * 64
            )
        return
    if change in ("mode", "seed", "clock", "budget"):
        for task in data["schedule"]["tasks"]:
            ctx = task["context"]
            if change == "mode":
                ctx["mode"] = "fresh_candidate"
            if change == "seed":
                ctx["seed"] += 1
            if change == "clock":
                ctx["clock"] = "2026-01-01T00:00:01Z"
            if change == "budget":
                ctx["budget"]["max_model_calls"] += 1
        # Remove terminal rows rather than changing their evidence to match modified contexts.
        data["rows"] = []
    elif change == "environment":
        data["schedule"]["environment_version"] = "changed"
    elif change == "policy":
        data["schedule"]["outcome_policy"]["version"] = "changed"
    elif change == "keys":
        data["schedule"]["trial_ids"] = ["other-trial"]
        for task in data["schedule"]["tasks"]:
            task["context"]["trial_id"] = "other-trial"
        data["rows"] = []
    with pytest.raises(ValueError):
        compare(old, BatchReport.model_validate_json(json.dumps(data)), loaded)


def test_private_markdown_escapes_untrusted_identifiers_and_html():
    loaded, schedule = population(count=1)
    card = report(batch(loaded, schedule), loaded)
    card = card.model_copy(
        update={"experiment_id": "<img src=x>![fetch](https://example.invalid)\n| injected |"}
    )
    rendered = render_scorecard(card)
    assert "<img" not in rendered and "![fetch]" not in rendered
    assert "&lt;img" in rendered and "\\| injected \\|" in rendered
