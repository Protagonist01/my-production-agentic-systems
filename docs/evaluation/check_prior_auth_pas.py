"""Run an actual pinned independent HL7 payer, invented PAS submit/readback/inquiry."""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from prior_auth.contracts import digest  # noqa: E402
from prior_auth.review_contracts import Principal  # noqa: E402

from prior_auth_demo import demo_request  # noqa: E402
from prior_auth_pas import (  # noqa: E402
    RI_COMMIT,
    Loopback,
    PasClient,
    bundle,
    checked_response,
    object_from,
)
from prior_auth_pipeline import prepare  # noqa: E402
from prior_auth_profiling import Profiler  # noqa: E402
from prior_auth_sandbox import Submission  # noqa: E402


def main(war: Path) -> None:
    war = war.resolve(strict=True)
    # Verify the built source, independently of the application fixture/transport.
    repository = war.parents[2]
    pin = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    if pin != RI_COMMIT:
        raise ValueError("reference-payer source pin differs")
    transport = Loopback("http://127.0.0.1:8081/fhir", timeout=10)
    # Refuse an existing unrelated listener; do not stop or impersonate it.
    import socket

    with socket.socket() as check:
        if check.connect_ex(("127.0.0.1", 8081)) == 0:
            raise ValueError("reference-payer port already occupied")
    with tempfile.TemporaryDirectory(prefix="pa-real-pas-") as temp:
        directory = Path(temp)
        with (directory / "server.log").open("wb") as log:
            server = subprocess.Popen(
                [
                    "java",
                    "-Xmx1536m",
                    "-Dserver.address=127.0.0.1",
                    "-Dserver.port=8081",
                    "-jar",
                    str(war),
                ],
                cwd=repository,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 480
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise ValueError("independent reference payer exited")
                    try:
                        metadata = object_from(transport("GET", "metadata", None))
                        if metadata.get("resourceType") == "CapabilityStatement":
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(3)
                else:
                    raise TimeoutError("reference-payer startup limit")
                raw = b"Invented demo only. AHI: 18 events/hour."
                imported = demo_request(raw)
                note = prepare(raw, imported, Profiler()).note
                assert note is not None
                request = Submission(
                    request_id="demo-real-pas",
                    case=imported.case,
                    case_version=1,
                    note_sha256=note.note_sha256,
                    policy_sha256=note.policy_sha256,
                )
                user = Principal(
                    username="demo-reviewer",
                    tenant_id="demo",
                    actor_id="demo-operator",
                    role="reviewer",
                    case_ids=(note.case_id,),
                )
                counts: list[str] = []

                def observed(method, path, payload):
                    counts.append(method + " " + path)
                    return transport(method, path, payload)

                client = PasClient(directory / "outbox.sqlite", observed)
                response = client.submit(user, request, note, current_version=1)
                assert response.state == "received", "reference submission not correlated"
                assert response.review_codes == ("A3",), (
                    "unknown invented service must not be certified"
                )
                assert client.submit(user, request, note, current_version=1) == response
                assert counts.count("POST Claim/$submit") == 1
                inquiry = checked_response(
                    transport("POST", "Claim/$inquire", bundle(request, note)),
                    digest(request.canonical_json()),
                    request,
                    transport,
                )
                assert inquiry.review_codes == ("A3",)
                print(
                    json.dumps(
                        {
                            "reference_commit": RI_COMMIT,
                            "actual_external_process": True,
                            "submissions": 1,
                            "durable_replay": True,
                            "inquiry": "correlated",
                            "submit_response_sha256": response.response_sha256,
                            "inquiry_response_sha256": inquiry.response_sha256,
                            "review_codes": list(response.review_codes),
                            "clinical_validation": False,
                            "commercial_payer": False,
                        }
                    )
                )
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--war", required=True, type=Path)
    args = parser.parse_args()
    try:
        main(args.war)
    except Exception as error:
        print("PAS integration refused: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
