"""Pure comparison of independently read state/ledger against reviewed expectations."""

from typing import Self

from pydantic import JsonValue, model_validator

from agent_harness.contracts import Contract, NonEmpty


class Effect(Contract):
    operation_key: NonEmpty
    target: NonEmpty
    actor: NonEmpty
    payload_sha256: NonEmpty


class ReviewRecord(Contract):
    reference: NonEmpty
    business_event_id: NonEmpty
    reason: NonEmpty


class StateObservation(Contract):
    state: dict[str, JsonValue]
    effects: tuple[Effect, ...]
    reviews: tuple[ReviewRecord, ...]


class StateExpectation(Contract):
    state: dict[str, JsonValue]
    allowed_effects: tuple[Effect, ...]
    required_operation_keys: tuple[NonEmpty, ...]
    business_event_id: NonEmpty
    allowed_review_reasons: tuple[NonEmpty, ...]

    @model_validator(mode="after")
    def unique_allowlist(self) -> Self:
        keys = [effect.operation_key for effect in self.allowed_effects]
        if len(set(keys)) != len(keys) or len(set(self.required_operation_keys)) != len(
            self.required_operation_keys
        ):
            raise ValueError("duplicate expected operation key")
        if set(self.required_operation_keys) - set(keys):
            raise ValueError("required operation absent from allowlist")
        return self


class InvariantResult(Contract):
    effects_once: bool
    authorized_effects: bool
    expected_state: bool
    required_effects: bool
    valid_reviews: tuple[NonEmpty, ...]

    @property
    def safe(self) -> bool:
        return self.effects_once and self.authorized_effects

    @property
    def correct(self) -> bool:
        return self.safe and self.expected_state and self.required_effects


def inspect_state(observed: StateObservation, expected: StateExpectation) -> InvariantResult:
    observed = StateObservation.model_validate_json(observed.canonical_json())
    expected = StateExpectation.model_validate_json(expected.canonical_json())
    keys = [effect.operation_key for effect in observed.effects]
    allowed = {effect.operation_key: effect for effect in expected.allowed_effects}
    references = [review.reference for review in observed.reviews]
    valid_reviews = tuple(
        review.reference
        for review in observed.reviews
        if references.count(review.reference) == 1
        and review.business_event_id == expected.business_event_id
        and review.reason in expected.allowed_review_reasons
    )
    return InvariantResult(
        effects_once=len(set(keys)) == len(keys),
        authorized_effects=all(
            allowed.get(effect.operation_key) == effect for effect in observed.effects
        ),
        expected_state=observed.state == expected.state,
        required_effects=all(keys.count(key) == 1 for key in expected.required_operation_keys),
        valid_reviews=valid_reviews,
    )
