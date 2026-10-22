"""Run current FakeAgent against a pinned, invented model-call transcript, offline."""

import argparse
import hashlib
import json
import sys
from importlib.resources import as_file, files
from pathlib import Path

from agent_harness.contracts import Failure, ModelMessage, ModelResponse
from agent_harness.gateway import ModelExchange
from agent_harness.offline_example import FakeAgent, FakeGateway, example_case, example_context
from agent_harness.recording import Recording, RecordingProvenance, load_recording, make_recording
from agent_harness.replay import ReplayBinding, ReplayMismatch, StrictReplayGateway

# Updated only through explicit fixture review; never learn a trusted pin from the input file.
INVENTED_DIGEST = "175fdcc50359cb5471bf292e15034fc250bf5ac724d05582b3d69bf429ac548d"
INVENTED_RESOURCE = "resources/replay/invented-v7.json"


class NetworkDisabledError(RuntimeError):
    """The standalone replay command refuses ordinary Python network operations."""


def _deny_network(event: str, arguments: tuple[object, ...]) -> None:
    if event in (
        "socket.connect",
        "socket.sendto",
        "socket.sendmsg",
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyaddr",
    ):
        raise NetworkDisabledError("outbound network is disabled during strict replay")


def invented_recording(code_revision: str, environment_lock: str) -> Recording:
    """Maintenance helper; synthetic in-process capture, not fresh provider evidence.

    Publication is separate and exclusive. The normal replay command never calls this.
    """
    rows: list[ModelExchange] = []
    for trial in ("trial-1", "trial-2"):
        context = example_context(code_revision, environment_lock).model_copy(
            update={"run_id": "invented-h3-capture", "trial_id": trial}
        )
        for occurrence in (1, 2, 3):
            failure = (
                Failure(
                    stage="model",
                    code="timeout",
                    message="Invented recorded timeout",
                    retryable=True,
                )
                if occurrence == 3
                else None
            )
            fake = FakeGateway(failure)
            # Execute the existing current agent to construct the actual request.
            result = FakeAgent().run(context, example_case().input, fake)
            rows.append(
                ModelExchange(
                    context=context,
                    occurrence=occurrence,
                    request=fake.requests[0],
                    response=ModelResponse(
                        provider="fake",
                        model="uppercase-v1",
                        usage=result.usage,
                        output=None
                        if failure
                        else ModelMessage(role="assistant", content=result.output),
                        failure=failure,
                        finish_reason=None if failure else "stop",
                    ),
                )
            )
    return make_recording(
        tuple(rows),
        RecordingProvenance(
            source_kind="synthetic",
            source_version="invented-h3-v1",
            snapshot_ref="invented-text-v1",
            policy_version="fake-text-policy-v1",
            scorer_version="fake-exact-text-v1",
            content_policy="invented-only-v1",
            content_review_ref="review:invented-h3-v1",
        ),
    )


def run_invented_replay(
    recording: Recording, *, code_revision: str, environment_lock: str
) -> dict[str, object]:
    bindings: list[ReplayBinding] = []
    seen: set[str] = set()
    for row in recording.exchanges:
        if row.context.trial_id in seen:
            continue
        seen.add(row.context.trial_id)
        source = row.context
        current = source.model_copy(
            update={
                "mode": "strict_replay",
                "run_id": "invented-h3-current",
                "versions": source.versions.model_copy(
                    update={
                        "code_revision": code_revision,
                        "candidate": "current-fake-agent",
                        "environment_lock": environment_lock,
                    }
                ),
            }
        )
        bindings.append(ReplayBinding(recorded=source, current=current))
    gateway = StrictReplayGateway(recording, tuple(bindings))
    calls = 0
    failures = 0
    for bound in bindings:
        for occurrence in (1, 2, 3):
            result = FakeAgent().run(bound.current, example_case().input, gateway)
            calls += 1
            if occurrence < 3:
                if result.outcome != "completed" or result.output != "HELLO, SHARED CONTRACTS":
                    raise ValueError("invented replay output check failed")
            elif result.failure is None or result.failure.code != "timeout":
                raise ValueError("invented replay failure check failed")
            else:
                failures += 1
    gateway.assert_complete()
    return {
        "mode": "strict_replay",
        "source_kind": "synthetic",
        "check": "invented-model-replay",
        "recording_sha256": recording.digest(),
        "current_code_revision": code_revision,
        "environment_lock": environment_lock,
        "capture_code_revision": recording.exchanges[0].context.versions.code_revision,
        "trials": len(bindings),
        "recorded_calls_consumed": calls,
        "recorded_timeouts_reproduced": failures,
        "outbound_provider_calls": 0,
        "quality_evaluation": False,
    }


def main() -> int:
    # This hook belongs to this standalone process and cannot be removed accidentally.
    # It is not an OS sandbox against arbitrary native code or subprocesses.
    sys.addaudithook(_deny_network)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--lockfile", required=True)
    args = parser.parse_args()
    resource = files("agent_harness").joinpath(INVENTED_RESOURCE)
    # as_file supports installed packages as well as source trees.
    try:
        with as_file(resource) as path:
            recording = load_recording(path, expected_digest=INVENTED_DIGEST)
        result = run_invented_replay(
            recording,
            code_revision=args.code_revision,
            environment_lock=hashlib.sha256(Path(args.lockfile).read_bytes()).hexdigest(),
        )
    except (ValueError, ReplayMismatch, OSError, NetworkDisabledError) as error:
        print(f"Replay failed ({type(error).__name__}); see fixture/context pins", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
