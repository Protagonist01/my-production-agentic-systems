# Immutable model recordings and strict replay — H3

H3 #17 implements reviewed JSON model-call fixtures and a separate `StrictReplayGateway`. H2's live gateway remains unchanged. Replay executes current caller code against captured model responses and typed failures. It never returns a previously stored final agent result and has no provider transport or live fallback.

## Run the bundled check

```powershell
python dev.py setup
python dev.py eval-replay
```

This command runs the current `FakeAgent` against six invented calls in two trials. Each trial consumes two identical successful requests and a recorded timeout. It checks the invented output/failure and requires all calls to be consumed. JSON stdout identifies `strict_replay`, synthetic source, capture/current code revisions, actual lock hash, fixture digest, six consumed calls, two reproduced timeouts and zero outbound provider calls. It explicitly reports `quality_evaluation=false`. Captured call usage is historical; it is not new model usage or a latency measurement.

The normal command does not author fixtures, read `.env.local`, initialize provider/trace clients or regenerate expected answers. It requires the exact recorded environment lock; a changed lock fails until an explicit reviewed fixture update. `--code-revision` supports actual source exports; the Git wrapper supplies HEAD plus `+dirty` otherwise. CI runs this command in all four quality cells. Setup/uv dependency acquisition can use the package network; the replay Python process blocks ordinary socket connect/DNS/datagram operations through an audit hook. This is not an OS sandbox against untrusted native code or child processes.

The command currently runs only this bundled wiring check. Use the reusable APIs below to integrate a real current agent. Domain batch manifests, independent state scoring and release gates belong to H5/H6/H9/H10; a successful replay is not a fresh model-quality result.

## Recording format and provenance

`agent_harness.recording.Recording` has schema version 1 and contains:

- `RecordingProvenance`: original/hybrid/synthetic source category and version, snapshot, policy/scorer versions, content policy and content-review reference.
- Ordered H2 `ModelExchange` rows: complete captured `RunContext`, allocated occurrence, model-v2 request and model-v2 output or typed failure, including observed usage and opaque ordered parts.

`make_recording(exchanges, provenance)` validates Python objects before canonical JSON copying, sorts by `(run, tenant, agent, case, trial, occurrence)` and detaches nested data. Each trial must have an unchanged context and contiguous occurrences starting at one. Every repeated request stays a distinct row. Asynchronous H2 completion order therefore does not scramble the allocated sequence. A missing middle occurrence fails; the exporter cannot know whether callers omitted an unobserved trailing attempt. Complete experiment accounting remains H6/H10.

Snapshot/policy must match the captured contexts. Route mismatch and successful revision mismatch fail; H2's typed invalid-response failure may retain an observed revision for diagnosis. Strict replay cannot be captured as new evidence. Offline-fake captures require synthetic provenance. A recording is nonempty and covers model calls only; zero-call case completeness belongs to the future manifest/runner.

## Sanitize before capture

Build reviewed model-visible input before dispatch, including tool results. Supply an explicit content policy/review reference. The exporter scans the entire document, including typed error messages and decoded JSON string leaves, for configured forbidden values and common credential forms. Review failure writes nothing and never echoes the offending text. Supply actual configured keys as forbidden values in memory; never place them in arguments, tracked code or review references.

This is not automatic PII discovery or a substitute for field review. References and source classifications are caller claims. Arbitrary secrets embedded in text, opaque binary signatures or hostile schema fields need the content owner's review. H8 owns broader redaction/export health. Only invented content is committed here; raw vertical fixtures stay in ignored storage with their own access controls.

There is deliberately no post-capture prompt normalization or redaction during matching. Changing a prompt after dispatch changes the experiment; modifying signed assistant history can invalidate a later request. If capture was unsafe, reject it and create a new explicitly sanitized capture. Preserve an actual provider's signed parts exactly within an appropriately protected reviewed fixture.

## Publish and load without replacement

```python
from pathlib import Path
from agent_harness.recording import load_recording, make_recording, write_recording

# exchanges came from the current gateway; provenance is reviewed explicitly.
recording = make_recording(exchanges, provenance)
digest = write_recording(Path("recordings/reviewed-v1.json"), recording,
                         forbidden_values=configured_secret_values)
# Store digest in a separately reviewed manifest, not inside the untrusted input file.
loaded = load_recording(Path("recordings/reviewed-v1.json"), expected_digest=digest)
```

The parent directory must already exist. `write_recording` writes a temporary sibling, flushes/fsyncs it and exclusively hard-links the complete file into the final path. Existing paths are never replaced, even if content matches. Concurrent writers have one winner; others get `FileExistsError`. Staging files are removed after success or failure. Filesystems without hard links fail visibly. An abrupt process crash can leave a staging file; no automatic recovery/cleanup or power-loss directory-durability guarantee is claimed.

The digest is SHA-256 of canonical UTF-8 JSON. Object-key/formatting differences may normalize to the same document; array order, text whitespace, types, unknown fields/versions and content remain significant. `load_recording` requires an external lowercase digest pin, enforces a 16 MiB byte limit, rejects duplicate keys/non-finite JSON, validates the complete contract and checks the pin before returning a detached snapshot. Changing the backing file after loading cannot alter the running session. A new load detects tampering against the pin.

This is application-level no-replacement, not write-once storage against administrators. Hashes prove agreement with a trusted pin, not origin, authorization or confidentiality. Do not accept an attacker-supplied file and attacker-supplied matching pin as trusted evidence.

## Bind captured conditions to current execution

Construct one `ReplayBinding(recorded=..., current=...)` for every captured trial. The recorded context must identify an actual complete trial in the fixture. Duplicate, missing or fabricated bindings fail before execution.

Current mode must be `strict_replay`. A new `run_id`, `versions.code_revision` and `versions.candidate` are allowed explicitly. Everything else stays exact: tenant, agent, case/trial/business-event, clock/deadline, seed, budget, data snapshot, policy and environment lock. Both contexts survive separately; replay never relabels the capture as a new current-code provider run. Caller IDs are not tenant authentication.

```python
from agent_harness.replay import ReplayBinding, StrictReplayGateway

binding = ReplayBinding(recorded=captured_context, current=current_replay_context)
gateway = StrictReplayGateway(loaded, (binding,))
result = current_agent.run(binding.current, reviewed_public_input, gateway)
gateway.assert_complete()  # required: a matching prefix is not a completed replay
```

`generate` looks up only that bound scope's next occurrence and compares the complete canonical request, not a fuzzy prompt match or global response cache. It advances only on a match and returns a detached response. Recorded timeouts/rate limits/etc. return their original typed model outcomes and historical unknown usage. Replay mismatches raise `ReplayMismatch` instead: code `replay_mismatch`, nonretryable, case/trial/call evidence, expected/actual fingerprints where available, no prompt/schema/body in the exception text. A mismatch poisons the session so catching it and trying the original request cannot create a pass. Invalid request contracts also poison it. Invalid caller context contracts raise validation errors before execution.

`assert_complete` checks every bound trial and seals the session. Unconsumed rows fail; extra requests and calls after completion fail. Independent sessions over one immutable fixture have independent cursors. Per-session locking allocates each occurrence once; scheduling of concurrent identical calls within one trial still belongs to the caller. Model replay does not pin mutable domain reads, reset domain writes, control all clocks or reproduce event scheduling. Those adapters must execute/reset and assert their actual state independently.

## Fixture maintenance and evidence

The bundled file is `harness/src/agent_harness/resources/replay/invented-v1.json`; its external pin lives in `replay_example.INVENTED_DIGEST`. It was authored through `invented_recording` at clean source **bce80f8c94ce81578767dacf4b95c5676662e6be** with lock SHA-256 **ab937ab9313389ded7eec95658a168f68f29ee5b9589f4ea8f3d498420c7ea72**. Digest: **72125a30c816dca9f2e72b3ac6f4fc5e718ee9386c95f6243db43ba19702ac2b**. This was synthetic in-process capture, with no provider requests.

To intentionally revise it, first commit the source that constructs the capture. Run the maintenance helper from that clean revision, publish to a new versioned filename with `write_recording`, inspect the invented content and provenance, then update the separately reviewed pin/resource reference in a new commit. Never regenerate a fixture on mismatch or during ordinary CI. Recorded files already in Git remain historical; creating a reviewed version is different from overwriting a runtime fixture.

`tests/test_replay.py` exercises exact request/history/context matching, isolated trials, repeated distinct answers, signed tool history, typed failures/unknown usage, sticky failures, completion, network denial, malformed/tampered fixtures, nested non-finite mutation, publication races and failed fsync/link cleanup. Local/hosted final results are recorded in the H3 PR and Build Book. No production traffic, live latency, domain correctness or fresh held-out quality claim follows from these checks.

## H4 controlled replay

H4 ReplayAttempts wraps only StrictReplayGateway, allowing current retry/admission logic to consume recorded attempts without SDK access. Always assert_complete afterward. ReplayMismatch remains an infrastructure exception after settlement/freeze, never a scored model response. Shared virtual time and complete domain state still require explicit adapters. See [controls](controls.md).
