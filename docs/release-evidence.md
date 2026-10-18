# Fresh recording and release evidence — H10

H10 #24 adds recording, comparison and release mechanisms on top of merged H9 main fd87750. The user selected **offline mechanism checks only**. Tests use invented inputs and provider mocks; no new live Gemini result, domain quality threshold or reviewed domain baseline is claimed. See [source study](code-study-release.md) and [Build Book Entry 23](../BUILD_BOOK.md#entry-23--fresh-dispatch-receipts-and-independently-reviewed-releases).

## Commands and explicit inputs

Run `python dev.py eval-record --help`, `python dev.py eval-compare --help` or `python dev.py eval-release --help`. The root wrapper passes arguments as a list to the locked installed module. The commands also work as `python -m agent_harness.release_cli <command>` in an installed harness environment.

All three require `--manifest`, `--manifest-pin`, `--candidate-spec`, `--candidate-spec-sha256` and a **new** `--output` directory. Pins are canonical SHA-256 values supplied separately by the reviewer/caller; obtaining a digest from a candidate file does not constitute review. Candidate, approval and release policy objects are strict, versioned JSON contracts. `--fault-plan` is required when the schedule/journal uses a reviewed H7 plan.

| Command | Additional inputs | Result |
|---|---|---|
| `eval-record` | `--schedule`, `--composition`, `--source-root` | New private journal, raw per-attempt receipts, sealed evidence.json; prints its digest and mock/provider origin |
| `eval-compare` | `--candidate-evidence`, `--candidate-evidence-sha256`, `--baseline-evidence`, `--baseline-evidence-sha256`, `--baseline-spec-sha256`, `--release-policy`, `--release-policy-sha256` | Private result.json with case regressions, no approval/release decision |
| `eval-release` | All comparison inputs plus `--baseline-approval` and `--baseline-approval-sha256` | Private result.json with allowed/blockers; blocked or invalid evidence exits nonzero |

Comparison/release optionally accept `--source-root` to check current source bytes against the supplied candidate inventory. They never dispatch a provider and their module entrypoint denies outbound network. Recording refuses old candidate/baseline response inputs and approval/policy inputs. There is no resume, cache, latest-baseline discovery, automatic promotion, deployment or approval-writing command. Comparison success means that comparison was generated, including any regressions it reports.

## Candidate construction and behavior binding

`CandidateSpec` requires candidate/code/lock identities; source_files (portable relative paths → byte SHA-256); separate prompt, model configuration, tools, policy, scorer and environment hashes; ExecutionPolicy; and the experiment recording_budget. `pin(spec)` from release_contracts hashes canonical JSON including every field. The externally expected spec pin must change for a behavior change. Any change requires a new **whole-population** capture. H10 does not claim precise slice dependency analysis or incremental evidence reuse.

The built-in trusted composition supports invented uppercase text only. Its RecordingConfig has composition (`invented-uppercase-mock` or explicit `invented-uppercase-gemini`), prompt and a ModelRequest template. The agent replaces template messages with a system prompt and the case's public user text. The complete template pin binds provider/model/revision/endpoint, parameters, schemas and tools; tools/structured output are rejected by this text-only composition. The mock route must be mock / invented-uppercase / in-process. Prompt bytes hash independently, tools hash the literal `no-tools`, policy hashes `fake-text-policy-v1`, scorer hashes `inspect.getsource(UppercaseScorer).encode()`, and environment hashes `h6-invented-files-v1:invented-state-v1` (UTF-8).

The built-in CLI requires every executing harness .py file in source_files under harness/src/agent_harness, plus uv.lock. It compares runtime module bytes, reviewed source-root bytes and the recorded lock hash. Inventory creation can use `sha256(path.read_bytes())`; review the inventory and external pin before recording. Code revision is an explicitly supplied provenance label; the inventory pins actual bytes. Do not label dirty/unreviewed source as an approved commit.

Generic library users supply a trusted FreshFactory returning agent, deadline-aware transport, admission policy and independent scorer registry. The recorder owns ProviderGateway and BoundedGateway; callers cannot pass a replay gateway through this interface. A fault-aware adapter must explicitly implement build_faults and wire H7 hooks. The trusted adapter must inventory **all** code/configuration dependencies and honestly identify mock/provider origin. This is a code-composition trust boundary, not a sandbox for candidate-selected Python or imports. Data never names a dynamically imported plugin.

## Fresh execution and budgets

The complete reviewed population must have exactly three distinct scheduled trial IDs, fresh_candidate mode, unique run IDs and max_parallel=1. Each context's candidate/code/lock must match the spec. The sum of per-trial call/token/cost ceilings must fit the external recording budget in one currency. BoundedGateway reserves before dispatch and bounds retries; unused capacity is not transferred between trials. This deliberately conservative partition avoids claiming a distributed quota from process-local controls.

Each H6 worker gets fresh controlled state. The owned ProviderGateway has no response cache, retry or fallback; BoundedGateway owns bounded retry policy. ReceiptGateway serializes attempts and saves execution ID, random nonce, actual timestamps and the complete ModelExchange before returning a response. Identical requests and answers remain separate dispatches. Different text is not proof of freshness. The direct deadline-aware transport runs inside H6's whole-worker deadline because an H6 daemon cannot spawn another isolated SDK child. Parent cleanup and independent scoring retain H6 semantics.

The explicit Gemini composition lazily imports the existing optional adapter and reads GEMINI_API_KEY / GEMINI_FREE_TIER_CONFIRMED from the environment. It uses the existing reviewed Free admission and token ceiling; budget partitions must cover that ceiling before each attempt. This path has **not** been exercised live for H10. No automatic .env loading, fallback or paid-provider selection occurs. Do not choose that composition for the offline acceptance exercise.

## Artifact verification and approval

The new private output contains journal/schedule.json, journal/rows/*.json, receipts/<context-pin>/<occurrence>.json and evidence.json. A separately created sibling `<output>-state` directory holds transient CLI file state and remains empty after successful cleanup. Exclusive creation prevents overwrite/resume. Failures can retain partial private artifacts for diagnosis; a retry needs new paths. Raw captures are not automatically published as H3 reviewed replay fixtures.

`read_evidence` checks external manifest/spec pins, canonical batch digest, reviewed manifest/fault plan, complete receipt inventory and raw byte hashes. Every scheduled trial needs contiguous attempt occurrences, unique nonces, matching exact context/execution identity and timestamps inside the recording interval. Every receipt must represent a dispatched call. Reported usage must equal observed attempt totals; unknown tokens/cost, missing receipts and budget excess cannot qualify as fresh evidence. Modified, missing or extra files fail. H9 scorecards separately verify wrapped scorer/source/group provenance and preserve scheduled denominators.

Before candidate capture, a reviewer supplies BaselineApproval with version, exact baseline evidence digest, exact release policy digest, reviewer/review_ref, approved_at and expires_at. The review must follow baseline completion and precede candidate recording. ReleasePolicy explicitly supplies version, H9 report policy (required and repeated cases), maximum evidence age, autonomous-completion floor and maximum observed review rate. These numeric values must be reviewed from the applicable domain baseline; H10 supplies no default quality floors.

The release gate rejects absent/wrong pins, expired/future evidence or approval, incompatible population/evaluator/policy/environment/state/fault treatment, reused execution/run IDs/nonces, mock evidence, incomplete or unsafe outcomes, any lost prior pass, any failed required trial and unmet quality/review limits. Zero critical violations is mandatory; a nonempty reviewed required-case set is required. Baseline and candidate match seeds, budgets, tenant/agent/business-event identity and allowed deadline duration. Their actual wall clocks may differ because they are distinct fresh runs. A changed evaluator/policy/environment needs a newly reviewed compatible baseline. A candidate can never bless its own execution by passing a self-comparison.

## Reproduce the offline checks

From a locked checkout run:

```powershell
uv run --locked --all-packages --link-mode copy pytest -q tests/test_release_recording.py tests/test_release_gates.py tests/test_release_cli.py tests/test_dev_commands.py
python dev.py check
python dev.py build
```

The recording tests actually spawn H6 workers with file state and provider mocks. The positive gate unit case uses explicitly artificial provider-labelled DTOs to exercise the branch; it is not saved as authentic provider evidence. Persisted mock runs are tested to block release. Test fixtures and numeric policies are invented and must never be promoted to a domain baseline. Exact measured acceptance results are maintained on #24 and in the Build Book.

## Limits and private handling

Hashes/receipts protect against accidental reuse and artifact changes relative to trusted external pins. They do not authenticate a human reviewer or defeat an operator who controls executable code, can forge every pin/approval and can relabel a mock transport. Review permissions and approval storage are external operational controls; no signing service or hostile-code isolation is implemented. Receipt timestamps rely on the trusted host clock. This is an evidence gate, not deployment authorization or proof of population safety.

Raw model inputs/outputs, provider IDs, private labels, state and approvals stay outside Git. New files/directories use 0600/0700 on POSIX; Windows inherits ACLs and needs a restricted parent directory. Results retain private case identities and are not H8's public-safe telemetry projection. Source snapshots, labels, domain scorers and an actual reviewed baseline remain prerequisites for a domain release. The [Langfuse CI/CD guidance](https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd) supports separately reviewed baselines, declared policy and case-level regression checks; this implementation adds no Langfuse service/SDK changes.
