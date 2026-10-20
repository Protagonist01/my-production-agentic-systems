"""Loopback support/review API and static workbench with scoped opaque sessions."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib.resources import files
from typing import Annotated, Any
from urllib.parse import urlsplit

import psycopg
from agent_harness.contracts import Budget, CandidateVersions, Contract, RunContext
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from olist_support.business_contracts import BusinessReview
from olist_support.console_auth import SESSION_SECONDS, AuthStore
from olist_support.console_cases import CaseStore
from olist_support.console_contracts import Decision, Principal, Resume, Submission
from olist_support.policy import POLICY_VERSION


class Login(Contract):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class BodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 16_384:
                await JSONResponse({"error": "request_too_large"}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break
        consumed = False

        async def limited() -> Message:
            nonlocal consumed
            if consumed:
                return await receive()
            consumed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, limited, send)


def create_app(
    cases: CaseStore,
    auth: AuthStore,
    *,
    origin: str,
    trial_id: str,
    code_revision: str,
    environment_lock: str,
    run_limit_minor: int,
) -> FastAPI:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or type(run_limit_minor) is not int
        or not 0 <= run_limit_minor <= 2**63 - 1
    ):
        raise ValueError("explicit loopback origin and nonnegative SIM run limit required")
    origin = origin.rstrip("/")
    suffix = hashlib.sha256(trial_id.encode()).hexdigest()[:12]
    session_cookie, csrf_cookie = "olist_session_" + suffix, "olist_csrf_" + suffix
    app = FastAPI(title="Olist support desk", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[parsed.hostname])

    def same_origin(request: Request) -> None:
        if (
            request.headers.get("origin") != origin
            or request.headers.get("content-type", "").split(";")[0] != "application/json"
        ):
            raise PermissionError("same-origin JSON required")

    def principal(request: Request, *, write: bool = False) -> Principal:
        csrf = None
        if write:
            same_origin(request)
            csrf = request.headers.get("x-csrf-token", "")
            if not 20 <= len(csrf) <= 128:
                raise PermissionError("request verification required")
        return auth.authenticate(request.cookies.get(session_cookie, ""), csrf)

    @app.middleware("http")
    async def headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; img-src "
                    "'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors"
                    " 'none'; form-action 'self'"
                ),
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.exception_handler(PermissionError)
    async def denied(request: Request, error: PermissionError) -> JSONResponse:
        return JSONResponse({"error": "access_or_session_denied"}, status_code=403)

    @app.exception_handler(LookupError)
    async def missing(request: Request, error: LookupError) -> JSONResponse:
        return JSONResponse({"error": "case_or_order_unavailable"}, status_code=404)

    @app.exception_handler(BusinessReview)
    async def conflict(request: Request, error: BusinessReview) -> JSONResponse:
        return JSONResponse({"error": "state_changed_or_action_ineligible"}, status_code=409)

    @app.exception_handler(psycopg.Error)
    async def unavailable(request: Request, error: psycopg.Error) -> JSONResponse:
        return JSONResponse(
            {"error": "state_service_unavailable_refresh_before_retry"}, status_code=503
        )

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(
            files("olist_support").joinpath("web/index.html").read_text(encoding="utf-8")
        )

    @app.get("/assets/{name}")
    def asset(name: str) -> Response:
        if name not in ("console.css", "console.js"):
            return Response(status_code=404)
        return Response(
            files("olist_support").joinpath("web/" + name).read_bytes(),
            media_type="text/css" if name.endswith("css") else "text/javascript",
        )

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    def health() -> JSONResponse:
        try:
            with cases.connection() as connection:
                connection.execute("SELECT 1 FROM olist_app.cases LIMIT 1")
            return JSONResponse({"status": "ready", "business_unit": "SIM"})
        except psycopg.Error:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    @app.post("/api/login")
    def login(payload: Login, request: Request) -> JSONResponse:
        same_origin(request)
        try:
            token, csrf, user = auth.login(payload.username, payload.password)
        except PermissionError:
            return JSONResponse({"error": "sign_in_failed"}, status_code=401)
        response = JSONResponse(
            {"principal": user.model_dump(mode="json"), "csrf_cookie": csrf_cookie}
        )
        response.set_cookie(
            session_cookie,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            path="/",
        )
        response.set_cookie(
            csrf_cookie, csrf, max_age=SESSION_SECONDS, httponly=False, samesite="strict", path="/"
        )
        return response

    @app.get("/api/session")
    def session(request: Request) -> dict[str, Any]:
        return {"principal": principal(request).model_dump(mode="json"), "csrf_cookie": csrf_cookie}

    @app.post("/api/logout")
    def logout(request: Request) -> JSONResponse:
        principal(request, write=True)
        auth.logout(request.cookies.get(session_cookie, ""))
        response = JSONResponse({"signed_out": True})
        response.delete_cookie(session_cookie, path="/")
        response.delete_cookie(csrf_cookie, path="/")
        return response

    @app.get("/api/orders")
    def orders(request: Request) -> list[dict[str, Any]]:
        user = principal(request)
        rows = []
        for order in user.order_ids:
            try:
                view, _, version = cases.business.order(user.grant(order), user.tenant_id, order)
            except LookupError:
                continue
            rows.append(
                {"order_id": order, "recorded_status": view.final_source_status, "version": version}
            )
        return rows

    @app.get("/api/cases")
    def listing(request: Request) -> list[dict[str, Any]]:
        user = principal(request)
        return [
            {
                "case_id": c.case_id,
                "order_id": c.order_id,
                "status": c.status,
                "intent": c.request.intent,
                "updated_at": c.updated_at.isoformat(),
            }
            for c in cases.listing(user)
        ]

    @app.post("/api/cases")
    def submit(payload: Submission, request: Request) -> dict[str, Any]:
        user = principal(request, write=True)
        user.require("operator")
        view, _, _ = cases.business.order(
            user.grant(payload.order_id), user.tenant_id, payload.order_id
        )
        now = datetime.now(UTC)
        context = RunContext(
            run_id=uuid.uuid4().hex,
            tenant_id=user.tenant_id,
            agent_id="olist-explicit-offline-intent",
            case_id="assigned-by-case-store",
            trial_id=trial_id,
            business_event_id="assigned-by-case-store",
            mode="offline_fake",
            clock=now,
            deadline=now + timedelta(minutes=2),
            seed=0,
            budget=Budget(
                max_model_calls=1, max_tokens=512, max_cost=Decimal("0"), cost_currency="USD"
            ),
            versions=CandidateVersions(
                code_revision=code_revision,
                candidate="olist-explicit-offline-intent-v1",
                data_snapshot=view.source_manifest_sha256,
                policy=POLICY_VERSION,
                environment_lock=environment_lock,
            ),
        )
        return cases.submit(user, payload, context, run_limit_minor=run_limit_minor).model_dump(
            mode="json"
        )

    @app.get("/api/cases/{case_id}")
    def detail(case_id: str, request: Request) -> dict[str, Any]:
        case, audit = cases.detail(principal(request), case_id)
        return {"case": case.model_dump(mode="json"), "events": audit}

    @app.post("/api/cases/{case_id}/decision")
    def decide(case_id: str, payload: Decision, request: Request) -> dict[str, Any]:
        return cases.decide(principal(request, write=True), case_id, payload).model_dump(
            mode="json"
        )

    @app.post("/api/cases/{case_id}/resume")
    def resume(case_id: str, payload: Resume, request: Request) -> dict[str, Any]:
        user = principal(request, write=True)
        case, _ = cases.detail(user, case_id)
        if case.status in ("processing", "needs_recovery"):
            return cases.run_request(user, case_id, run_limit_minor=run_limit_minor).model_dump(
                mode="json"
            )
        return cases.resume(
            user, case_id, payload.action_digest, run_limit_minor=run_limit_minor
        ).model_dump(mode="json")

    @app.post("/api/cases/{case_id}/reevaluate")
    def reevaluate(case_id: str, request: Request) -> dict[str, Any]:
        return cases.reevaluate(principal(request, write=True), case_id).model_dump(mode="json")

    return app
