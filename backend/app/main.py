import logging
from base64 import b64decode
from secrets import compare_digest
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from backend.app.api.routes import build_router
from backend.app.core.config import Settings
from backend.app.schemas.api import APIError, ErrorResponse

logger = logging.getLogger(__name__)
BODY_LIMIT = 4096
AUTH_CHALLENGE = 'Basic realm="Delivery Intelligence", charset="UTF-8"'


def error_response(request_id, status, code, message):
    payload = ErrorResponse(error=APIError(code=code, message=message), request_id=request_id)
    return JSONResponse(status_code=status, content=payload.model_dump())


def authorized(header: str, expected: bytes) -> bool:
    scheme, _, token = header.partition(" ")
    if scheme.casefold() != "basic":
        return False
    try:
        return compare_digest(b64decode(token, validate=True), expected)
    except ValueError:
        return False


class BoundAskBody:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "POST"
                or scope["path"] not in {"/api/ask", "/api/ask/stream"}):
            await self.app(scope, receive, send)
            return
        data = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(data) + len(chunk) > BODY_LIMIT:
                response = error_response(scope["state"]["request_id"], 413, "body_too_large",
                                          "The request exceeds the 4096-byte limit.")
                await response(scope, receive, send)
                return
            data.extend(chunk)
            if not message.get("more_body", False):
                break
        received = False

        async def replay():
            nonlocal received
            if received:
                return await receive()
            received = True
            return {"type": "http.request", "body": bytes(data), "more_body": False}

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    access_password = settings.app_access_password
    if settings.app_require_access_password and access_password is None:
        raise ValueError("APP_REQUIRE_ACCESS_PASSWORD requires a server-side APP_ACCESS_PASSWORD.")
    expected_credentials = (
        f"copilot:{access_password.get_secret_value()}".encode("utf-8") if access_password is not None else None
    )
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s %(message)s")
    app = FastAPI(title="Agentic AI Business Analytics Copilot", version="1.0.0")
    app.add_middleware(BoundAskBody)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = perf_counter()
        try:
            health_probe = request.url.path == "/api/health" and request.method in {"GET", "HEAD"}
            if expected_credentials is not None and not health_probe and not authorized(
                request.headers.get("Authorization", ""), expected_credentials,
            ):
                response = error_response(request.state.request_id, 401, "authentication_required",
                                          "Enter the access password for this workspace.")
                response.headers["WWW-Authenticate"] = AUTH_CHALLENGE
            else:
                response = await call_next(request)
        except Exception as error:
            logger.error("api_failure request_id=%s error_type=%s",
                         request.state.request_id, type(error).__name__)
            response = error_response(request.state.request_id, 500, "internal_error",
                                      "The request could not be completed.")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if expected_credentials is not None:
            response.headers["Cache-Control"] = "private, no-store"
        route = request.scope.get("route")
        logger.info("api_request request_id=%s route=%s status=%d elapsed_ms=%.2f",
                    request.state.request_id, getattr(route, "path", "unmatched"), response.status_code,
                    (perf_counter() - started) * 1000)
        return response

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"],
                       expose_headers=["X-Request-ID"])

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError):
        return error_response(request.state.request_id, 422, "invalid_request",
                              "Supply a question between 3 and 600 characters and a supported mode.")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = "service_unavailable" if error.status_code == 503 else "http_error"
        response = error_response(request.state.request_id, error.status_code, code, str(error.detail))
        response.headers.update(error.headers or {})
        return response

    app.include_router(build_router(settings))
    dist = settings.frontend_dist
    if (dist / "index.html").is_file() and (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def dashboard():
            return FileResponse(dist / "index.html", headers={
                "Cache-Control": "no-cache",
                "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
                "frame-ancestors 'none'; form-action 'self'",
            })

    return app


app = create_app()
