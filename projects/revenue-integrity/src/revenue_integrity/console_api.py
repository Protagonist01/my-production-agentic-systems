"""Loopback-only Revenue review API; browser inputs never carry authority."""

import hashlib
import secrets
from collections.abc import Callable
from importlib.resources import files
from typing import Annotated, Any
from urllib.parse import urlsplit

import psycopg
from agent_harness.contracts import Contract
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import Field
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from revenue_integrity.console_auth import SESSION_SECONDS, AuthStore
from revenue_integrity.console_contracts import Decision, Principal, Submission, Trim, Wake
from revenue_integrity.console_service import ConsoleService
from revenue_integrity.operation_contracts import BusinessReview, ChangeCommand


def wire(value: Any) -> Any:
    """JSON numbers cannot preserve signed64-bit amounts in browser JavaScript."""
    if type(value) is int:
        return str(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


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
    service: ConsoleService,
    auth: AuthStore,
    *,
    origin: str,
    trial_id: str,
    publish: Callable[[Wake, bool], None] | None = None,
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
    ):
        raise ValueError("explicit loopback origin required")
    origin = origin.rstrip("/")
    suffix = hashlib.sha256(trial_id.encode()).hexdigest()[:12]
    cookie, csrf_cookie = "revenue_session_" + suffix, "revenue_csrf_" + suffix
    app = FastAPI(
        title="Revenue integrity workbench", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[parsed.hostname])

    def same_origin(request: Request) -> None:
        if (
            request.headers.get("origin") != origin
            or request.headers.get("host") != parsed.netloc
            or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")
        ):
            raise PermissionError("request origin denied")

    def principal(request: Request, *, mutation: bool = False) -> Principal:
        if mutation:
            same_origin(request)
        csrf = request.headers.get("x-csrf-token") if mutation else None
        if mutation and not csrf:
            raise PermissionError("request verification required")
        return auth.authenticate(request.cookies.get(cookie, ""), csrf)

    @app.middleware("http")
    async def headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self'; frame-ancestors 'none'; "
                    "base-uri 'none'; form-action 'self'"
                ),
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
        return JSONResponse({"error": "record_or_proposal_unavailable"}, status_code=404)

    @app.exception_handler(BusinessReview)
    async def conflict(request: Request, error: BusinessReview) -> JSONResponse:
        return JSONResponse({"error": "state_changed_or_action_requires_review"}, status_code=409)

    @app.exception_handler(ValueError)
    async def bad(request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse({"error": "invalid_action"}, status_code=422)

    @app.exception_handler(psycopg.Error)
    async def unavailable(request: Request, error: psycopg.Error) -> JSONResponse:
        return JSONResponse(
            {"error": "state_service_unavailable_refresh_before_retry"}, status_code=503
        )

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(
            files("revenue_integrity")
            .joinpath("web/index.html")
            .read_text(encoding="utf-8")
            .replace("__CSRF_COOKIE__", csrf_cookie)
        )

    @app.get("/assets/{name}")
    def asset(name: str) -> Response:
        if name not in ("console.css", "console.js"):
            return Response(status_code=404)
        return Response(
            files("revenue_integrity").joinpath("web/" + name).read_bytes(),
            media_type="text/css" if name.endswith("css") else "text/javascript",
        )

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.post("/api/login")
    def login(payload: Login, request: Request) -> JSONResponse:
        same_origin(request)
        token, csrf, user = auth.login(payload.username, payload.password)
        response = JSONResponse(
            {"username": user.username, "role": user.role, "tenant_id": user.tenant_id}
        )
        response.set_cookie(
            cookie, token, httponly=True, samesite="strict", max_age=SESSION_SECONDS, path="/"
        )
        response.set_cookie(
            csrf_cookie, csrf, httponly=False, samesite="strict", max_age=SESSION_SECONDS, path="/"
        )
        return response

    @app.post("/api/logout")
    def logout(request: Request) -> JSONResponse:
        principal(request, mutation=True)
        auth.logout(request.cookies.get(cookie, ""))
        response = JSONResponse({"signed_out": True})
        response.delete_cookie(cookie)
        response.delete_cookie(csrf_cookie)
        return response

    @app.get("/api/session")
    def session(request: Request) -> JSONResponse:
        user = principal(request)
        return JSONResponse(
            {"username": user.username, "role": user.role, "tenant_id": user.tenant_id}
        )

    @app.get("/api/workbench")
    def workbench(request: Request) -> JSONResponse:
        return JSONResponse(wire(service.workbench(principal(request))))

    def dispatch(wake: Wake, reviewed: bool) -> str:
        if publish is None:
            return "disabled"
        try:
            publish(wake, reviewed)
        except Exception:
            # The canonical proposal is already committed. A relay outage cannot
            # undo it; a sweep or explicit apply recovers with the same key.
            return "pending_recovery"
        return "sent"

    @app.post("/api/proposals")
    def propose(payload: Submission, request: Request) -> JSONResponse:
        result = service.propose(principal(request, mutation=True), payload)
        return JSONResponse(
            wire(
                {
                    **result.model_dump(mode="json"),
                    "event_dispatch": dispatch(
                        Wake(
                            tenant_id=result.command.tenant_id,
                            actor_id=result.proposer_id,
                            operation_id=result.command.business_operation_id,
                        ),
                        False,
                    ),
                }
            )
        )

    @app.post("/api/proposals/{operation_id}/review")
    def review(operation_id: str, payload: Decision, request: Request) -> JSONResponse:
        result = service.review(
            principal(request, mutation=True),
            operation_id,
            approve=payload.decision == "approve",
            digest=payload.action_digest,
        )
        return JSONResponse(
            wire(
                {
                    **result.model_dump(mode="json"),
                    "event_dispatch": dispatch(
                        Wake(
                            tenant_id=result.command.tenant_id,
                            actor_id=result.proposer_id,
                            operation_id=result.command.business_operation_id,
                        ),
                        True,
                    ),
                }
            )
        )

    @app.post("/api/proposals/{operation_id}/apply")
    def apply(operation_id: str, request: Request) -> JSONResponse:
        user = principal(request, mutation=True)
        if user.role != "operator":
            raise PermissionError("operator required")
        result = service.store.apply(
            user.grant(), operation_id, run_id="web-" + secrets.token_hex(16)
        )
        return JSONResponse({"ledger_id": result.ledger_id, "committed": True})

    @app.post("/api/trim")
    def trim(payload: Trim, request: Request) -> JSONResponse:
        user = principal(request, mutation=True)
        if user.role != "operator":
            raise PermissionError("operator required")
        command = ChangeCommand(
            tenant_id=user.tenant_id,
            business_operation_id=payload.operation_id,
            kind="crm_trim",
            resource_id=payload.resource_id,
            expected_version=payload.expected_version,
        )
        result = service.store.trim(user.grant(), command, run_id="web-" + secrets.token_hex(16))
        return JSONResponse({"ledger_id": result.ledger_id, "committed": True})

    @app.post("/api/sweep")
    def sweep(request: Request) -> JSONResponse:
        user = principal(request, mutation=True)
        return JSONResponse({"expired": len(service.store.sweep(user.grant()))})

    return app
