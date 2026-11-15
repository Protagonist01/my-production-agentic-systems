"""Reuse the protected evidence desk with explicit synthetic demo citation cards."""

from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from prior_auth.review_api import create_app
from prior_auth.review_auth import AuthStore
from prior_auth.review_contracts import Principal
from prior_auth.review_store import ReviewStore

from prior_auth_evidence_cards import EvidenceReader


class EvidenceStore(ReviewStore):
    def snapshot(self, user: Principal, case_id: str) -> dict[str, Any]:
        snapshot = super().snapshot(user, case_id)
        snapshot["demo_mode"] = "synthetic-records-not-clinically-validated"
        with self.transaction() as c:
            modes = c.execute(
                "SELECT DISTINCT s.document->>'mode' AS mode "
                "FROM prior_auth_demo.attempts a JOIN prior_auth_demo.scopes s USING(scope_id) "
                "WHERE a.tenant_id=%s AND a.case_id=%s AND a.case_version=%s",
                (user.tenant_id, case_id, snapshot["version"]),
            ).fetchall()
        snapshot["current_attempt_modes"] = [r["mode"] for r in modes]
        snapshot["evidence_cards"] = []
        if snapshot["result"] is not None and snapshot["status"] != "assessing":
            base = ReviewStore(self.connect, clock=self.clock)
            snapshot["evidence_cards"] = [
                card.model_dump(mode="json")
                for card in EvidenceReader(base).cards(
                    user, case_id, expected_version=snapshot["version"]
                )
            ]
        return snapshot


def demo_app(store: ReviewStore, auth: AuthStore, *, origin: str, trial_id: str) -> FastAPI:
    # Auth/origin/CSRF/host checks and mutations remain those of the original desk.
    service = EvidenceStore(store.connect, clock=store.clock)
    app = create_app(service, auth, origin=origin, trial_id=trial_id)
    # Replace presentation routes only. Do not wrap or bypass private API handlers.
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", None) not in {"/", "/assets/{name}"}
    ]
    import hashlib

    csrf_cookie = "prior_auth_csrf_" + hashlib.sha256(trial_id.encode()).hexdigest()[:12]

    @app.get("/")
    def index() -> HTMLResponse:
        text = files("prior_auth").joinpath("web/index.html").read_text(encoding="utf-8")
        text = text.replace("__CSRF_COOKIE__", csrf_cookie).replace(
            "Illustrative records · Provisional labels<br>"
            "Qualified clinical review remains required.",
            "Synthetic portfolio demo<br>Not clinically validated · No insurer approval.",
        )
        return HTMLResponse(text)

    @app.get("/assets/{name}")
    def assets(name: str) -> Response:
        if name not in {"console.js", "console.css"}:
            return Response(status_code=404)
        original = files("prior_auth").joinpath("web/" + name).read_bytes()
        if name == "console.js":
            original += b"\n" + Path(__file__).with_suffix(".js").read_bytes()
        return Response(
            original, media_type="text/javascript" if name.endswith("js") else "text/css"
        )

    return app
