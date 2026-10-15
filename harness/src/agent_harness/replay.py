"""Strict scoped replay: execute current callers, never dispatch or fall back."""

import threading
from typing import Self

from pydantic import model_validator

from agent_harness.contracts import (
    Contract,
    EvidenceReference,
    Failure,
    ModelRequest,
    ModelResponse,
    RunContext,
)
from agent_harness.gateway import ModelExchange
from agent_harness.recording import Recording, Scope, trial_scope


class ReplayBinding(Contract):
    recorded: RunContext
    current: RunContext

    @model_validator(mode="after")
    def compatible_context(self) -> Self:
        if self.current.mode != "strict_replay" or self.recorded.mode == "strict_replay":
            raise ValueError("replay binding needs captured and strict-replay contexts")
        expected = self.recorded.model_dump(mode="json")
        actual = self.current.model_dump(mode="json")
        # These changes identify execution, not the captured dependency conditions.
        for value in (expected, actual):
            value.pop("run_id")
            value.pop("mode")
            value["versions"].pop("code_revision")
            value["versions"].pop("candidate")
        if expected != actual:
            raise ValueError("replay context differs from captured dependency conditions")
        return self


class ReplayMismatch(RuntimeError):
    """Infrastructure failure: cannot be mistaken for a recorded model outcome."""

    def __init__(
        self,
        context: RunContext,
        occurrence: int,
        reason: str,
        *,
        expected_fingerprint: str | None = None,
        actual_fingerprint: str | None = None,
    ) -> None:
        self.context = context
        self.occurrence = occurrence
        self.reason = reason
        self.expected_fingerprint = expected_fingerprint
        self.actual_fingerprint = actual_fingerprint
        self.failure = Failure(
            stage="model",
            code="replay_mismatch",
            message=reason,
            retryable=False,
            evidence=(
                EvidenceReference(
                    reference=f"replay:{context.run_id}:{context.case_id}:{context.trial_id}:{occurrence}",
                    kind="model",
                ),
            ),
        )
        # Never echo prompt/schema/tool/error bodies. Structured context remains available.
        super().__init__(
            f"{reason}; case={context.case_id}; trial={context.trial_id}; call={occurrence}"
        )


class StrictReplayGateway:
    """One independent, thread-safe consumption session over a detached recording.

    It deliberately has no live transport, credentials, imports of provider SDKs,
    or mutable fixture handle. Always call assert_complete after running current code.
    """

    def __init__(self, recording: Recording, bindings: tuple[ReplayBinding, ...]) -> None:
        validated = Recording.model_validate(recording)
        self._recording = Recording.model_validate_json(validated.canonical_json())
        self.recording_digest = self._recording.digest()
        self._rows: dict[Scope, list[ModelExchange]] = {}
        for row in self._recording.exchanges:
            self._rows.setdefault(trial_scope(row.context), []).append(row)
        self._bindings: dict[Scope, ReplayBinding] = {}
        recorded_scopes: set[Scope] = set()
        for binding in bindings:
            binding = ReplayBinding.model_validate_json(
                ReplayBinding.model_validate(binding).canonical_json()
            )
            current_scope = trial_scope(binding.current)
            source_scope = trial_scope(binding.recorded)
            if current_scope in self._bindings or source_scope in recorded_scopes:
                raise ValueError("duplicate replay binding")
            if source_scope not in self._rows or (
                self._rows[source_scope][0].context != binding.recorded
            ):
                raise ValueError("binding does not identify a captured trial")
            self._bindings[current_scope] = binding
            recorded_scopes.add(source_scope)
        if recorded_scopes != set(self._rows):
            raise ValueError("every recorded trial requires exactly one explicit binding")
        self._positions = dict.fromkeys(self._bindings, 0)
        self._failed: ReplayMismatch | None = None
        self._closed = False
        self._lock = threading.Lock()

    def _fail(
        self,
        context: RunContext,
        occurrence: int,
        reason: str,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self._failed = ReplayMismatch(
            context,
            occurrence,
            reason,
            expected_fingerprint=expected,
            actual_fingerprint=actual,
        )
        raise self._failed

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        context = RunContext.model_validate_json(
            RunContext.model_validate(context).canonical_json()
        )
        request = ModelRequest.model_validate_json(
            ModelRequest.model_validate(request).canonical_json()
        )
        scope = trial_scope(context)
        with self._lock:
            if self._failed is not None:
                raise self._failed
            position = self._positions.get(scope, 0)
            binding = self._bindings.get(scope)
            if self._closed:
                self._fail(context, position + 1, "replay session already completed")
            if binding is None or binding.current != context:
                self._fail(context, position + 1, "unbound or changed replay context")
            assert binding is not None
            rows = self._rows[trial_scope(binding.recorded)]
            if position >= len(rows):
                self._fail(context, position + 1, "no recorded call at this occurrence")
            row = rows[position]
            if row.request.canonical_json() != request.canonical_json():
                self._fail(
                    context,
                    position + 1,
                    "model request differs from recording",
                    row.request.fingerprint(),
                    request.fingerprint(),
                )
            self._positions[scope] = position + 1
            return ModelResponse.model_validate_json(row.response.canonical_json())

    def assert_complete(self) -> None:
        """Seal success only when every bound occurrence was consumed without mismatch."""
        with self._lock:
            if self._failed is not None:
                raise self._failed
            for scope, binding in self._bindings.items():
                position = self._positions[scope]
                rows = self._rows[trial_scope(binding.recorded)]
                if position != len(rows):
                    self._fail(binding.current, position + 1, "recorded calls remain unconsumed")
            self._closed = True
