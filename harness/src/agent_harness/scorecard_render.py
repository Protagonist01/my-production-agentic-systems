"""Escaped private Markdown reports; JSON retains the full structured evidence."""

import html

from agent_harness.scorecard_contracts import Comparison, Ratio, Scorecard, Summary


def escape(value: object) -> str:
    text = html.escape(str(value).replace("\r", " ").replace("\n", " "), quote=True)
    return "".join("\\" + char if char in "\\`*_{}[]()#+.!|-" else char for char in text)


def rate(value: Ratio) -> str:
    percent = f"{100 * value.value:.2f}%" if value.value is not None else "undefined"
    return f"{value.numerator}/{value.denominator} ({percent}; unknown {value.unknown})"


def _summary(summary: Summary) -> list[str]:
    rows = ["| Measure | Numerator / denominator |", "|---|---|"]
    for label, value in (
        ("Autonomous completion on eligible trials", summary.autonomous_completion),
        ("Confirmed correct completion or appropriate review", summary.confirmed_success),
        ("Observed review requests", summary.observed_review),
        ("Appropriate review on required-review trials", summary.appropriate_review),
        ("Unnecessary review on non-required-review trials", summary.unnecessary_review),
        ("Observed unsafe trials", summary.observed_violations),
        ("Complete independent evidence", summary.evidence_complete),
    ):
        rows.append(f"| {label} | {rate(value)} |")
    risk = summary.safety_uncertainty
    rows += [
        "",
        f"Scheduled: {summary.scheduled_trials}; present: {summary.present_rows}; "
        f"missing: {summary.missing_rows}.",
        "",
        "Group safety: "
        + str(risk.observed_event_groups)
        + "/"
        + str(risk.groups)
        + f" observed event groups; {risk.unknown_groups} unknown groups. "
        f"Conditional 95% interval envelope: [{risk.lower}, {risk.upper}].",
        "Independent comparable groups are assumed, not verified. Repeated trials do not "
        "increase the group count. This is not proof of zero risk.",
        "",
        "Categories: " + escape(summary.category_counts),
        "",
        "Usage totals: an unknown total retains its observed subtotal below.",
        "",
        "| Usage | Complete total | Known subtotal | Unknown trials |",
        "|---|---|---|---|",
    ]
    usage = summary.usage
    for name, total, known, unknown in (
        (
            "Model calls",
            usage.model_calls,
            usage.known_model_calls,
            usage.unknown_model_call_trials,
        ),
        (
            "Input tokens",
            usage.input_tokens,
            usage.known_input_tokens,
            usage.unknown_input_token_trials,
        ),
        (
            "Output tokens",
            usage.output_tokens,
            usage.known_output_tokens,
            usage.unknown_output_token_trials,
        ),
    ):
        rows.append(
            f"| {name} | {total if total is not None else 'unknown'} | {known} | {unknown} |"
        )
    rows += ["", "| Currency | Known cost subtotal |", "|---|---|"]
    for currency, cost in usage.known_cost_by_currency.items():
        rows.append(f"| {escape(currency)} | {escape(cost)} |")
    rows += [
        "",
        f"Complete cost: {escape(usage.cost)} {escape(usage.cost_currency)}; "
        f"unknown-cost trials: {usage.unknown_cost_trials}. "
        "Different currencies are never summed.",
        "",
        "Complete run cost / autonomous completions: "
        + escape(usage.cost_per_autonomous_completion),
    ]
    return rows


def render_scorecard(report: Scorecard) -> str:
    lines = [
        "# Private scorecard",
        "",
        f"Experiment: {escape(report.experiment_id)}. Mode: {escape(report.mode)}. "
        "Freshness is not verified by reporting.",
        "",
        f"Candidate: {escape(report.candidate)}; code: {escape(report.code_revision)}; "
        f"environment lock: {escape(report.environment_lock)}.",
        "",
        f"Reporter: {escape(report.reporter_version)} / {escape(report.reporter_code_revision)}; "
        f"manifest: {escape(report.manifest.sha256)}; batch: {escape(report.batch_sha256)}.",
        "",
        "This report contains private case/group identities and labels. It omits raw "
        "inputs, outputs, hidden state and scorer/exception text. It is not a release decision.",
        "",
        "## Overall",
        "",
        *_summary(report.overall),
        "",
        "## Fault outcomes",
        "",
        *_summary(report.fault_outcomes),
        "",
        "## Repeated-trial correctness",
        "",
        escape(report.repeated_correctness.status),
    ]
    repeated = report.repeated_correctness.all_three_correct
    if repeated is not None:
        lines += [
            "",
            "All three declared fresh-mode trials correct: " + rate(repeated),
            "Actual fresh-provider provenance remains an H10 check.",
        ]
    lines += [
        "",
        "## Slices",
        "",
        "Overlapping tags and fault kinds must not be added together.",
        "",
        "| Dimension | Label | Completion | Violations | Unknown groups | 95% upper |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.slices:
        s = item.summary
        lines.append(
            f"| {escape(item.dimension)} | {escape(item.label)} | "
            f"{rate(s.autonomous_completion)} | {rate(s.observed_violations)} | "
            f"{s.safety_uncertainty.unknown_groups} | {s.safety_uncertainty.upper} |"
        )
    lines += [
        "",
        "## Cases",
        "",
        "| Case | Split / source | Required | Trial categories |",
        "|---|---|---|---|",
    ]
    for case in report.cases:
        facts = "; ".join(f"{f.trial_id}: {f.category}" for f in case.trials)
        lines.append(
            f"| {escape(case.case_id)} | {escape(case.split)} / "
            f"{escape(case.source_kind)} | {case.required_case} | {escape(facts)} |"
        )
    return "\n".join(lines) + "\n"


def render_comparison(report: Comparison) -> str:
    lines = [
        "# Private paired comparison",
        "",
        f"Baseline: {escape(report.baseline_sha256)}. "
        f"Candidate: {escape(report.candidate_sha256)}.",
        "",
        f"Mode: {escape(report.mode)}; completion delta: {report.completion_delta}.",
        "",
        "Baseline approval is not established by comparison. No release decision is performed.",
        "",
        "Newly failing required cases: " + escape(report.newly_failing_required_cases),
        "",
        "| Case | Required | Baseline passes | Candidate passes | Regressed trials | "
        "New unsafe | New unverified |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in report.cases:
        lines.append(
            f"| {escape(case.case_id)} | {case.required} | "
            f"{case.baseline_passes}/{case.trials} | {case.candidate_passes}/{case.trials} | "
            f"{escape(case.regressed_trial_ids)} | {escape(case.new_unsafe_trial_ids)} | "
            f"{escape(case.new_unverified_trial_ids)} |"
        )
    return "\n".join(lines) + "\n"
