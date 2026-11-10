"""Accepted triage labor/value comparisons. Estimates never become observed savings."""

from collections import Counter, defaultdict
from typing import Annotated, Literal, Self

from agent_harness.contracts import WireContract
from pydantic import AwareDatetime, Field, model_validator

from cfpb_triage.triage_contracts import Id


class WorkSample(WireContract):
    case_id: Id
    family: Id
    actor: Id
    arm: Literal["manual", "assisted"]
    basis: Literal["human_attested", "invented", "estimated"]
    arrived: AwareDatetime
    accepted: AwareDatetime | None = None
    initial_seconds: Annotated[float, Field(ge=0)]
    correction_seconds: Annotated[float, Field(ge=0)]
    oversight_seconds: Annotated[float, Field(ge=0)]
    correct: bool | None = None
    hourly_labor: Annotated[float, Field(ge=0)] | None = None
    recurring_machine_cost: Annotated[float, Field(ge=0)] | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.accepted and (self.accepted - self.arrived).total_seconds() < self.active:
            raise ValueError("nonoverlapping active labor must fit elapsed interval")
        return self

    @property
    def active(self) -> float:
        return self.initial_seconds + self.correction_seconds + self.oversight_seconds


def economic_report(
    samples: tuple[WorkSample, ...], *, scheduled_per_arm: int, study_cost: float | None = None
) -> dict[str, object]:
    if scheduled_per_arm < 1 or (study_cost is not None and study_cost < 0):
        raise ValueError("positive schedule and nonnegative study cost required")
    if len({(s.case_id, s.arm) for s in samples}) != len(samples):
        raise ValueError("duplicate work sample")
    exposed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for s in samples:
        exposed[s.actor, s.family].add(s.arm)
    if any(len(arms) > 1 for arms in exposed.values()):
        raise ValueError("same actor saw same family in both arms")
    groups = {a: Counter(s.family for s in samples if s.arm == a) for a in ("manual", "assisted")}
    comparable = groups["manual"] == groups["assisted"] and bool(groups["manual"])
    summaries: dict[str, dict[str, object]] = {}
    for arm in ("manual", "assisted"):
        rows = [s for s in samples if s.arm == arm]
        if len(rows) > scheduled_per_arm:
            raise ValueError("work observations exceed schedule")
        known_cost = (
            all(s.hourly_labor is not None and s.recurring_machine_cost is not None for s in rows)
            and bool(rows)
            and len({s.currency for s in rows}) == 1
        )
        total_cost = (
            sum(
                s.active / 3600 * (s.hourly_labor or 0) + (s.recurring_machine_cost or 0)
                for s in rows
            )
            if known_cost
            else None
        )
        summaries[arm] = {
            "scheduled": scheduled_per_arm,
            "observed": len(rows),
            "unfinished_or_missing": scheduled_per_arm - sum(s.accepted is not None for s in rows),
            "correct_accepted": sum(s.accepted is not None and s.correct is True for s in rows),
            "unknown_correctness": sum(s.correct is None for s in rows),
            "active_seconds": sum(s.active for s in rows),
            "correction_seconds": sum(s.correction_seconds for s in rows),
            "oversight_seconds": sum(s.oversight_seconds for s in rows),
            "elapsed_seconds": sum(
                (s.accepted - s.arrived).total_seconds() for s in rows if s.accepted is not None
            ),
            "recurring_cost": total_cost,
            "cost_per_correct_accepted": (
                total_cost / sum(s.accepted is not None and s.correct is True for s in rows)
                if total_cost is not None and any(s.accepted and s.correct is True for s in rows)
                else None
            ),
        }
    currencies = {s.currency for s in samples}
    bases = {s.basis for s in samples}
    complete = comparable and all(
        summaries[a]["observed"] == scheduled_per_arm
        and summaries[a]["unfinished_or_missing"] == 0
        and summaries[a]["correct_accepted"] == scheduled_per_arm
        for a in summaries
    )
    observed = complete and bases == {"human_attested"} and len(currencies) == 1
    manual, assisted = summaries["manual"], summaries["assisted"]
    saved = sum(s.active if s.arm == "manual" else -s.active for s in samples) if observed else None
    net = (
        sum(
            (1 if s.arm == "manual" else -1)
            * (s.active / 3600 * (s.hourly_labor or 0) + (s.recurring_machine_cost or 0))
            for s in samples
        )
        if (
            observed
            and manual["recurring_cost"] is not None
            and assisted["recurring_cost"] is not None
        )
        else None
    )
    return {
        "arms": summaries,
        "comparable_family_mix": comparable,
        "complete_correct": complete,
        "basis": sorted(bases),
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "observed_active_seconds_saved": saved,
        "observed_recurring_net_saving": net,
        "one_time_study_cost": study_cost,
        "claim_limit": "human attestations, not randomized causal proof or complaint resolution",
    }


def shadow_stop(
    *,
    critical_effect: bool,
    missing_rate: float,
    review_backlog: int,
    p95_seconds: float | None,
    maximum_missing_rate: float,
    maximum_backlog: int,
    maximum_p95_seconds: float,
) -> tuple[str, ...]:
    """Explicit caller-approved limits; no implicit production target or silent retuning."""
    if (
        not 0 <= missing_rate <= 1
        or not 0 <= maximum_missing_rate <= 1
        or review_backlog < 0
        or maximum_backlog < 0
        or maximum_p95_seconds <= 0
    ):
        raise ValueError("invalid shadow limits")
    reasons = []
    if critical_effect:
        reasons.append("critical_effect")
    if missing_rate > maximum_missing_rate:
        reasons.append("missing_results")
    if review_backlog > maximum_backlog:
        reasons.append("review_backlog")
    if p95_seconds is None or p95_seconds > maximum_p95_seconds:
        reasons.append("latency_unknown_or_over_limit")
    return tuple(reasons)
