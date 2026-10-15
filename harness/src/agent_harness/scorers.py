"""Explicit trusted plugin composition; manifest data never names Python imports."""

from dataclasses import dataclass
from typing import Annotated, Self

from pydantic import Field, model_validator

from agent_harness.cases import CaseEntry, Identifier, LoadedManifest, ManifestPin, Split
from agent_harness.contracts import Agent, AgentResult, Contract, ModelGateway, RunContext
from agent_harness.evaluation import CaseReport, EvalCase, Scorer, ScoreResult, run_case


class ScorerCompatibility(Contract):
    snapshot_ref: Identifier
    policy_version: Identifier


class ScorerSpec(Contract):
    scorer_id: Identifier
    version: Identifier
    compatible: Annotated[tuple[ScorerCompatibility, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_compatibility(self) -> Self:
        pairs = [(item.snapshot_ref, item.policy_version) for item in self.compatible]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate scorer compatibility")
        return self


@dataclass(frozen=True)
class _RegisteredScorer:
    spec: ScorerSpec
    implementation: Scorer

    def check(self, entry: CaseEntry) -> None:
        if (entry.scorer_id, entry.case.scorer_version) != (self.spec.scorer_id, self.spec.version):
            raise ValueError("scorer identity/version differs from case")
        pair = entry.case.snapshot_ref, entry.case.policy_version
        if pair not in {(item.snapshot_ref, item.policy_version) for item in self.spec.compatible}:
            raise ValueError("scorer incompatible with case snapshot/policy")

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        # Isolate nested dictionaries from plugin mutation. Trusted code is not sandboxed.
        private_case = EvalCase.model_validate_json(case.canonical_json())
        private_result = AgentResult.model_validate_json(result.canonical_json())
        scores = tuple(
            ScoreResult.model_validate_json(score.canonical_json())
            for score in self.implementation.score(private_case, private_result)
        )
        if not scores:
            raise ValueError("registered scorer returned no scores")
        if any(score.scorer_version != self.spec.version for score in scores):
            raise ValueError("returned scorer version differs from registration")
        if len({score.metric for score in scores}) != len(scores):
            raise ValueError("registered scorer returned duplicate metrics")
        return scores


class ScorerRegistry:
    """Compose once, then bind a reviewed population before invoking any agent."""

    def __init__(self) -> None:
        self._scorers: dict[tuple[str, str], _RegisteredScorer] = {}

    def register(self, spec: ScorerSpec, implementation: Scorer) -> None:
        spec = ScorerSpec.model_validate_json(spec.canonical_json())
        key = spec.scorer_id, spec.version
        if key in self._scorers:
            raise ValueError("scorer identity/version already registered")
        if not callable(getattr(implementation, "score", None)):
            raise TypeError("scorer must implement score")
        self._scorers[key] = _RegisteredScorer(spec, implementation)

    def bind(self, loaded: LoadedManifest) -> "BoundEvaluation":
        bindings = {}
        for entry in loaded.manifest.entries:
            key = entry.scorer_id, entry.case.scorer_version
            scorer = self._scorers.get(key)
            if scorer is None:
                raise ValueError("scorer identity/version is not registered")
            scorer.check(entry)
            bindings[entry.case.case_id] = scorer
        return BoundEvaluation(loaded, bindings)


class ManifestCaseReport(Contract):
    manifest: ManifestPin
    group_id: Identifier
    split: Split
    scorer_id: Identifier
    report: CaseReport


class BoundEvaluation:
    """A fixed population/binding snapshot, not a batch runner or release gate."""

    def __init__(self, loaded: LoadedManifest, bindings: dict[str, _RegisteredScorer]) -> None:
        self._loaded = loaded
        self._bindings = dict(bindings)

    def run_case(
        self, context: RunContext, case_id: str, agent: Agent, gateway: ModelGateway
    ) -> ManifestCaseReport:
        entry = self._loaded.entry(case_id)
        scorer = self._bindings[case_id]
        scorer.check(entry)
        report = run_case(context, entry.case, agent, gateway, scorer)
        return ManifestCaseReport(
            manifest=self._loaded.pin,
            group_id=entry.group_id,
            split=entry.split,
            scorer_id=entry.scorer_id,
            report=report,
        )
