"""Protected walkthrough routes composed with the existing Revenue session/review API."""

import hashlib
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from revenue_integrity.console_api import create_app, wire
from revenue_integrity.console_auth import AuthStore
from revenue_integrity.console_contracts import Principal
from starlette.types import ASGIApp

from revenue_demo import Analyze, DemoService, Propose
from revenue_profiled_runtime import ProfiledHTTP

ROOT = Path(__file__).resolve().parent


def application(
    service: DemoService,
    auth: AuthStore,
    *,
    origin: str,
    trial_id: str,
    allow_public_https: bool = False,
) -> ASGIApp:
    origin = origin.removesuffix("/")
    app = create_app(
        service, auth, origin=origin, trial_id=trial_id, allow_public_https=allow_public_https
    )
    suffix = hashlib.sha256(trial_id.encode()).hexdigest()[:12]
    cookie = "revenue_session_" + suffix
    csrf_cookie = "revenue_csrf_" + suffix
    expected_host = urlsplit(origin).netloc

    def user(request: Request, *, mutation: bool = False) -> Principal:
        csrf = request.headers.get("x-csrf-token") if mutation else None
        if mutation and (
            request.headers.get("origin") != origin
            or request.headers.get("host") != expected_host
            or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")
            or not csrf
        ):
            raise PermissionError("same-origin authenticated request required")
        return auth.authenticate(request.cookies.get(cookie, ""), csrf)

    @app.get("/walkthrough")
    def page() -> HTMLResponse:
        return HTMLResponse(
            (ROOT / "revenue_demo_web.html")
            .read_text(encoding="utf-8")
            .replace("__CSRF_COOKIE__", csrf_cookie)
        )

    @app.get("/walkthrough-assets/{name}")
    def asset(name: str) -> Response:
        if name not in ("revenue_demo_web.js", "revenue_demo_web.css"):
            return Response(status_code=404)
        return Response(
            (ROOT / name).read_text(encoding="utf-8"),
            media_type="application/javascript" if name.endswith(".js") else "text/css",
        )

    @app.get("/walkthrough-api/cases")
    def catalog(request: Request) -> list[dict[str, object]]:
        return cast(list[dict[str, object]], wire(service.list_cases(user(request))))

    @app.post("/walkthrough-api/analyze")
    def analyze(payload: Analyze, request: Request) -> dict[str, object]:
        return cast(dict[str, object], wire(service.analyze(user(request, mutation=True), payload)))

    @app.post("/walkthrough-api/propose")
    def propose(payload: Propose, request: Request) -> dict[str, object]:
        return cast(
            dict[str, object],
            wire(
                service.propose_checked(user(request, mutation=True), payload).model_dump(
                    mode="json"
                )
            ),
        )

    @app.get("/walkthrough-api/timing")
    def timing(request: Request) -> dict[str, object]:
        user(request)
        # Shared timing contains no document/user/SQL content; do not expose trace identifiers.
        snapshot = service.recorder.snapshot()
        return {
            "stages": snapshot["stages"],
            "complete": snapshot["complete"],
            "provider_internal_time_known": False,
        }

    return ProfiledHTTP(app, service.recorder)
