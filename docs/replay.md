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

The historical file is `harness/src/agent_harness/resources/replay/invented-v1.json`; it remains byte-for-byte unchanged. It was authored through `invented_recording` at clean source **bce80f8c94ce81578767dacf4b95c5676662e6be** with lock SHA-256 **ab937ab9313389ded7eec95658a168f68f29ee5b9589f4ea8f3d498420c7ea72**. Digest: **72125a30c816dca9f2e72b3ac6f4fc5e718ee9386c95f6243db43ba19702ac2b**. This was synthetic in-process capture, with no provider requests.

To intentionally revise it, first commit the source that constructs the capture. Run the maintenance helper from that clean revision, publish to a new versioned filename with `write_recording`, inspect the invented content and provenance, then update the separately reviewed pin/resource reference in a new commit. Never regenerate a fixture on mismatch or during ordinary CI. Recorded files already in Git remain historical; creating a reviewed version is different from overwriting a runtime fixture.

`tests/test_replay.py` exercises exact request/history/context matching, isolated trials, repeated distinct answers, signed tool history, typed failures/unknown usage, sticky failures, completion, network denial, malformed/tampered fixtures, nested non-finite mutation, publication races and failed fsync/link cleanup. Local/hosted final results are recorded in the H3 PR and Build Book. No production traffic, live latency, domain correctness or fresh held-out quality claim follows from these checks.

## H4 controlled replay

H4 ReplayAttempts wraps only StrictReplayGateway, allowing current retry/admission logic to consume recorded attempts without SDK access. Always assert_complete afterward. ReplayMismatch remains an infrastructure exception after settlement/freeze, never a scored model response. Shared virtual time and complete domain state still require explicit adapters. See [controls](controls.md).


## H8 proposed dependency-lock fixture update

PR #78 includes an explicit new invented fixture/pin for review. The optional telemetry package extra changes lock metadata, so the historical fixture correctly refuses the current lock. ReplayBinding and request matching remain unchanged. The bundled command now proposes `replay_example.INVENTED_RESOURCE` = `resources/replay/invented-v2.json` and external `INVENTED_DIGEST` = **0d05fc31a93abe4872000aeb81895d5bbf0529f1f427b849edc16e366ce2432e**, captured through the in-process FakeGateway helper at source **08ba28e28e9ac01a946648cdc3411ae65451833b** with actual lock **5458e34a1d1ac88d11b478235fa3bc4912ee272e24b81f7b51b866fd49412dbc**. Its provenance is synthetic / invented-h8-lock-v2, with review reference review:pr-78-invented-v2. That reference identifies this proposed PR review; it does not claim user approval before merge.

Both resources remain packaged. The six model requests/responses, including two typed timeouts, agree with the historical fixture. No real provider output was captured or substituted. The old resource retains its original pin and still rejects the new lock. Future lock changes again require explicit fixture/pin review rather than silently rebinding recorded conditions or regenerating during normal replay. H8's final source/PR evidence records actual replay results separately.


## O4 + O5 explicit workflow-lock fixture update

The new optional workflow dependencies change the actual lock to `8bbcb51e6362da19b3c100440d4b5f9e2644f7829b47561c874526d0a772f3f3`. The first complete local check correctly rejected the v2 fixture. Keep ReplayBinding strict and preserve both historical resources. At clean committed capture source `8d10f3a6161c008d4e27c4c9ba11496c443f2fc3`, execute the existing in-process `invented_recording` helper and exclusively publish `resources/replay/invented-v3.json`. Its external reviewed content pin is **434e62b9e97f6164b41412d94317c257914d6e6d8c6ec5adeedc286db78ea345**; provenance is synthetic / invented-o4-o5-lock-v3 with review reference review:proposed-o4-o5-invented-v3. This names the proposed review, not prior user approval.

All six requests/responses were compared directly with v2 and are equal, including two typed timeouts. Only capture context/provenance changes to declare the new dependency conditions. All three resources remain packaged; tests pin both old versions and require them to reject the current lock. Normal replay never captures or changes a trusted pin. No provider call or real source content enters this fixture.


## O6 + O7 explicit web-lock fixture update

The optional web extra changes the actual lock to `c52f7636fe16a7898642cb4324538741611099dcc5b6e814913643aee7c8c7a3`. At clean committed source `c656ef564048ff02870c6966ab23da77cbf041d2`, explicitly execute the existing invented capture helper and exclusively publish `resources/replay/invented-v4.json`. The external content pin is **d92e2271b50913a4c276b9028d2441dd90a147223310225ee7438c862fbc19dd**; provenance is synthetic / invented-o6-o7-lock-v4, review reference review:proposed-o6-o7-invented-v4. This proposes the fixture for review, not prior approval. All six requests/responses match v3 exactly. Preserve all three historical resources/pins and require each to reject the current lock. Normal replay never generates or changes a fixture; no provider call or real source record enters this capture.


## Revenue batch explicit certificate-lock fixture update

On 2026-10-21 the locked dependency audit reported `PYSEC-2026-4320` against certifi 2026.7.22. Updating only certifi to 2026.10.19 changes the actual lock to `6e5895cc5fc20f51ea5479695329094b41843d1e5b5a4c911df76347dde5a7c6`. Historical replay remains strict; none of the four earlier recordings is rebound to the new lock.

At clean committed capture source `8e25d2e02d7cf5d8ef788f762b912056cdde1936`, execute the existing in-process `invented_recording` helper and exclusively publish `resources/replay/invented-v5.json`. Its separately reviewed content pin is **da8f943e0c0c1af861bda3a6a6a08960e6870c09a1080207083cc681557dc1dd**; provenance is synthetic / invented-revenue-certifi-lock-v5 with review reference review:proposed-revenue-certifi-invented-v5. This identifies the proposed review, not prior user approval. Direct comparison confirms all six requests/responses equal v4, including the two typed timeouts. No provider dispatch or original contract data enters this capture.

The normal replay command uses v5 without generating fixtures. All four historical files retain their independently pinned bytes and tests require them to reject the new lock. This update establishes software replay under the corrected dependency conditions; it does not establish fresh model quality or domain release acceptance.


## R6 explicit event-adapter lock update

The optional Revenue events adapter adds pinned Inngest 0.5.19 and jcs 0.2.1, without changing existing dependency versions. Lock `f1d00addeaefbbd946abea7b25b0e039473109bd6f146515e35ab9b20e7609e5` requires a separate invented capture. At clean source `28cdf485ed7cac4e1d5460b555baafea1bf9cbc4`, the maintenance helper exclusively published `resources/replay/invented-v6.json`, content pin **4224a610495d5bc657240e5a4dc6c44c08318149fc0f4534b8716763da603883**, synthetic provenance `invented-revenue-events-lock-v6` and proposed content review `review:proposed-revenue-events-invented-v6`. This is a proposal for user review, not a claim of prior approval.

All six request/response pairs were compared directly with v5 and are identical, including two typed timeouts. All five historical resources/pins remain packaged and explicitly reject the new environment lock. Normal replay never captures or learns a trusted pin; no provider call or source-domain record enters this fixture. The fixed-lock audit found no known vulnerabilities before integrated acceptance.


## Supply workflow extra: explicit invented v7 capture

The Supply optional workflow extra reuses existing LangGraph/Inngest pins but changes workspace lock identity to `b0d264aeb155915511202ced1338d6840546ae6cfe8c1b18e1553f2683edf266`. At clean capture source `ba962c6cdec3a7f7f694a2eaf92d705c324e7e3e`, explicitly execute the in-process maintenance helper and exclusively publish `resources/replay/invented-v7.json`, reviewed-content pin **175fdcc50359cb5471bf292e15034fc250bf5ac724d05582b3d69bf429ac548d**, synthetic source `invented-supply-workflow-lock-v7`, proposed review `review:proposed-supply-workflow-invented-v7`. This proposed content is part of user PR review, not a claim of prior approval. All six requests/responses match v6 exactly, including two typed timeouts. Historical v1–v6 resources remain immutable and reject the current lock; replay itself never writes/rebinds a recording. Zero provider calls and no original source content enter this fixture.


## Supply web extra: explicit invented v8 capture

S5 adds web extra metadata without changing dependency versions. At clean source `733a3d2d6d700d237402f5184bf50637e18d6736`, capture six in-process invented exchanges with lock `cb27dc9b03a7a09967eeba2005abdb6447565cfbe4bbcda7b41d1c1063328f10`. All request/response canonical bytes equal v7, including two timeouts. Preserve v1-v7 bytes and reject their historical locks. New resource `invented-v8.json` has external digest `307a0797021be1cc1804d87f4f4d5bfd2fbb2c937c880b79dfc2b151c321431e`. This is fixture maintenance with zero provider calls, not model-quality evidence.


## Supply standalone web dependency correction: invented v9

The web extra now explicitly includes the already-pinned LangGraph assessment dependency. Isolated web-only import reproduced its absence before correction. Capture at clean source `966b196dd4bd07d169e232541e082cd0f93e71f2` uses lock `e9694f444898bc4e06e70080c42634a7e39e91305b1543b5965b884af215f6c1` and digest `f2ee896a12d8a7858c165db559f70b8775d86007a14ee969f8ba97fdc5986fa4` in `invented-v9.json`. Six request/response pairs equal v8; retain v1-v8 bytes and reject their historical locks. No dependency versions, replay matching rules or provider evidence change.


## Prior Auth web/workflow extras: explicit invented v10

The P4/P5 extras reuse pinned LangGraph/FastAPI/Uvicorn versions but change the lock to e261f8bcee3a14ab2061b79ea3a43a2ff3793e96607c97c286561b63730e9c4d. At clean source4ee75bc6a7d227b2c5469bfda8f60637d69a78c4, explicitly run the existing in-process capture helper and exclusively publish invented-v10.json with digest c3a6804a93739740a196a44aaed66af31a564faa6c1b9b61600b82386b985f08. The generic invented-h3-v1 provenance remains declared synthetic; this proposed content is part of user PR review, not prior user approval. All six request/response pairs equal v9, including two timeouts. Preserve v1–v9 and test historical-lock rejection. Zero provider calls and no source notes enter fixture maintenance; normal replay never captures or rebinds it.
