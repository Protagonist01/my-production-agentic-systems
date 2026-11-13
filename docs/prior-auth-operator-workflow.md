# Authenticated Prior Auth operator workflow

Implementation dated 2026-11-13, based on main `257c9b9`/PR157. This extends the opt-in
[document pipeline](prior-auth-document-pipeline.md) with executable local commands.
It preserves frozen domain/harness packages, old schemas, baseline code/captures and
release gates. Only invented imports are enabled. There is no model-provider switch
or public upload endpoint in this command.

## Run an invented case

Use the checked-out source root and the existing locked environment. Docker/Postgres
must be running for bootstrap and account/import/worker/inspection commands. A draft
can be created without Docker, credentials or provider access. Choose a new private
directory outside **every** Git checkout; the example path below is illustrative.

```powershell
$demo = 'D:/document/.cache/production-agents/prior-auth/my-operator-demo-v1'
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo draft-demo --directory $demo
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo bootstrap
uv run --locked --all-packages --link-mode copy python -m prior_auth.review_cli --root . --trial pa-operator-demo account --principal "$demo/principal.json"
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo import --username demo-reviewer --request "$demo/request.json" --source "$demo/source.txt"
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo receipt --username demo-reviewer --case demo-case --document demo-document
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo worker
```

Account provisioning prompts for a new password of 15–128 characters. Import and
inspection prompt for the existing reviewer password. No password/token/CSRF value
belongs in an argument, source manifest, stdout or repository. Bootstrap creates the
legacy reviewer schema plus the additive intake schema using the existing workspace
administrator; ordinary import/inspection uses the restricted runtime role. It does
not replace account provisioning or silently grant the caller a reviewer identity.

The default worker always routes to qualified review with zero provider calls. The
legacy checker records its missing-candidate/assessment-failure flag for this intentional
abstention; it is not evidence that a live model failed. For the explicitly invented,
unqualified development baseline, use `worker --baseline conflict-rules-v3`. There is
no `--live-gemini` flag; the original provider allowance/stop is unchanged. One invocation
claims at most one job and preserves the existing lease/version/recovery behavior.

For the existing protected reviewer UI:

```powershell
uv run --locked --all-packages --link-mode copy python -m prior_auth.review_cli --root . --trial pa-operator-demo serve
```

Use its configured loopback origin and the same provisioned reviewer account. This
change does not expose document uploads or change the existing desk's clinical controls.

## Import boundary and replay

`ImportRequest` still carries trusted case/subject/provider/payer/plan/service bindings,
exact source/normalization/policy pins and reviewed binding/relevance/redaction references.
PDF/OCR additionally needs extraction review. These assertions do not authenticate
clinical expertise, prove relevance from prose or make an arbitrary file safe.

The command authenticates before reading manifests or document files. It then checks
the principal's write capability, case membership and tenant before opening the source
or running a native parser. Reads are bounded: 2MB request, 10MB source and 64KB optional
native-tools configuration. Paths must resolve outside Git. The manifest and source
are each read once; `prepare` verifies the exact source bytes against their pin.

For PDF/OCR, the trusted operator may supply `--native-tools private-tools.json`:

```json
{
  "version": "prior-auth-native-tools-v1",
  "pdfinfo": "/usr/bin/pdfinfo",
  "pdftotext": "/usr/bin/pdftotext",
  "pdftoppm": "/usr/bin/pdftoppm",
  "tesseract": "/usr/bin/tesseract",
  "timeout_seconds": 30
}
```

Use actual absolute executable paths on the run host. This is trusted command
configuration, never an attachment field or web request. Native worker isolation is
still required before hostile uploads; path validation is not an OS sandbox.

`IntakeStore.accept` remains the single atomic handoff. Import prints only the fixed
intake outcome, recorded version, zero provider attempts and payload-free timing. A
rejected import still records a receipt even if no legacy case exists. Repeating the
exact same import/document identity replays its original receipt; a changed payload
under that identity is a conflict. A supplemental request needs the current wait and
expected version. Rejected material never appends to a note or schedules assessment.

Sessions are revoked in a finally block on success and failure. Error messages include
only the exception class and fixed guidance, not passwords, note text, filenames copied
from errors, parser stderr or validation input. If logout/database access fails after
commit, the command can report failure even though intake committed. Inspect/replay
the same receipt identity rather than creating a new import blindly.

## Inspect exact source locations

Receipt lookup is case/tenant scoped and works for accepted and rejected documents.
It returns hashes, a fixed decision, version and timestamp. Source lookup returns
locations only—no quote, note body or document body.

For the unredacted invented draft, its normalization pin is the initial current note pin:

```powershell
$notePin = (Get-Content "$demo/request.json" -Raw | ConvertFrom-Json).normalization_sha256
uv run --locked --all-packages --link-mode copy python prior_auth_operator.py --root . --trial pa-operator-demo locate --username demo-reviewer --case demo-case --document demo-document --note-sha $notePin --start 0 --end 3
```

For other imports, obtain the actual current note SHA and Unicode offsets from the
protected case view; redaction changes its text hash. Offsets are half-open character
positions, not byte offsets. After a supplement changes the note, an old pin is refused.
The reader joins saved document, receipt and current case in one SQL snapshot, verifies
receipt/source/version agreement and the exact saved-document substring, then translates
current-note offsets to normalized document regions. Thus an earlier document can still
be located after append, using the new current note pin. A rejected document has no source
record, and a range in the synthetic separator is not accepted as that document's evidence.

`imported_version` and `current_version` distinguish the original admission from later
case versions. Text/structured locations use adapter locators; PDF boxes use points and
OCR boxes use rendered-image pixels. Location integrity does not establish clinical
meaning, patient identity, policy applicability or OCR correctness.

## Exposed conflict regression

The old `prior_auth_scorecards.rules` function is unchanged. The separately named
`prior-auth-conflict-rules-v3` variant routes distinct visible hourly AHI/RDI values to
qualified review. Equal decimal values retain the original rules behavior. The guard
recognizes a limited explicit grammar; different units, time periods and clinical
relationships need broader evidence. Even legitimately different measurements can
trigger conservative review. The variant decides neither which number is correct nor
whether treatment or coverage is appropriate. Non-invented notes are not qualified for
this baseline and return review.

The actual comparison uses only the two already exposed `conflict-0/1` inputs. It
verifies source/request pins against a separate execution of the unchanged old diagnostic
runner and retains the same proposed route references and unknown criterion states.

```powershell
uv run --locked --all-packages --link-mode copy python prior_auth_operator_comparison.py run --directory D:/private/new-conflict-capture
uv run --locked --all-packages --link-mode copy python prior_auth_operator_comparison.py readback --directory D:/private/new-conflict-capture
```

The second command runs in a separate process, verifies source/output hashes and
recomputes all three selected scorecards. Actual 2026-11-13 capture: original rules
0/2 proposed-route agreement, always-review 2/2, conflict-rules 2/2; all 14 criterion
reference slots stay unknown for each comparator. New-variant latency stays unknown.
The six observations are exposed development regressions, not a representative sample,
independent clinical truth, provider comparison, confidence claim or release study.
Original historical captures remain untouched; the underlying 26-case runner is not
relabeled as improved. There are zero provider attempts and qualification remains false.

## Verification and remaining work

Focused tests cover auth-before-read, role/tenant rejection, logout on error, bounded
private files, exclusive drafts, quiet credential errors, unsupported provider flags,
read authorization, numeric ambiguity, immutable original baseline and capture tampering.
Required real SQL witnesses cover authenticated replay/session revocation, rejected
receipts without cases, current-note/prefix/source-pin fencing after supplementation,
and actual offline operator worker publication. Local Docker is unavailable; hosted
acceptance must supply the actual SQL result before merge.

Clinical reference qualification, final frozen model evaluation, an authenticated external
HL7/SMART sandbox, native-worker isolation and deployment/recovery remain separate work.
This workflow prepares the operational path and does not close release issue #51.
