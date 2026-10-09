import asyncio
import hashlib
import hmac
import secrets
import time
from http.cookies import SimpleCookie

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.contracts import strict_json
from app.errors import AppError
from app.frontend import ASSETS


class Sessions:
    def __init__(self) -> None:
        self.secret = secrets.token_bytes(32)  # Ephemeral; never written to disk or logs.

    def sign(self, value: str) -> str:
        return hmac.new(self.secret, value.encode(), hashlib.sha256).hexdigest()

    def issue(self) -> tuple[str, str]:
        value = f"{int(time.time())}.{secrets.token_hex(24)}"
        cookie = value + "." + self.sign(value)
        return cookie, self.csrf(cookie)

    def csrf(self, cookie: str) -> str:
        return self.sign("csrf:" + cookie)

    def valid(self, cookie: str) -> bool:
        try:
            timestamp, nonce, signature = cookie.split(".")
            age = time.time() - int(timestamp)
            return (
                0 <= age <= 3600
                and len(nonce) == 48
                and hmac.compare_digest(signature, self.sign(timestamp + "." + nonce))
            )
        except (ValueError, TypeError):
            return False


class BoundaryMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, sessions: Sessions) -> None:
        self.app, self.settings, self.sessions = app, settings, sessions
        self.active_uploads = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        upload = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") in {"/api/captures", "/api/turns", "/api/speech/transcribe"}
        )
        if upload and self.active_uploads >= 4:
            response = JSONResponse(
                AppError(
                    503, "upload_busy", "Too many concurrent uploads. Retry shortly."
                ).payload(),
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return
        if upload:
            self.active_uploads += 1
        try:
            await self.process(scope, receive, send)
        finally:
            if upload:
                self.active_uploads -= 1

    async def process(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                await self.app(scope, receive, send)
            return
        headers_list = scope.get("headers", [])
        headers = {
            key.decode("latin1").lower(): value.decode("latin1") for key, value in headers_list
        }
        public_asset = scope["path"] in ASSETS and scope["method"] in {"GET", "HEAD"}
        csp = b"default-src 'none'; frame-ancestors 'none'"
        if public_asset:
            csp += (
                b"; script-src 'self'; style-src 'self'; connect-src 'self';"
                b" img-src 'self' blob:; media-src 'self' blob:; worker-src 'self';"
                b" base-uri 'none'; form-action 'self'; object-src 'none'"
            )

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", csp),
                    (b"permissions-policy", b"camera=(self), microphone=(self), geolocation=()"),
                ]
            await send(message)

        try:
            if any(
                sum(k.decode("latin1").lower() == name for k, _ in headers_list) > 1
                for name in ("host", "origin", "cookie", "content-length", "x-csrf-token")
            ):
                raise AppError(
                    400, "duplicate_header", "Duplicate security headers are not allowed."
                )
            if headers.get("host") not in self.settings.hosts:
                raise AppError(403, "host_denied", "Use the configured localhost address.")
            if "origin" in headers and headers["origin"] not in self.settings.origins:
                raise AppError(403, "origin_denied", "Cross-origin access is not allowed.")
            if headers.get("sec-fetch-site") in ("cross-site", "same-site"):
                raise AppError(403, "origin_denied", "Use the same local origin.")
            path, method = scope["path"], scope["method"]
            if not public_asset and path not in ("/api/session", "/api/status"):
                cookies = SimpleCookie()
                try:
                    cookies.load(headers.get("cookie", ""))
                except Exception as exc:
                    raise AppError(401, "session_required", "Open a local session first.") from exc
                morsel = cookies.get("app_session")
                cookie = morsel.value if morsel else ""
                if not self.sessions.valid(cookie):
                    raise AppError(401, "session_required", "Open a local session first.")
                if method not in ("GET", "HEAD", "OPTIONS") and not hmac.compare_digest(
                    headers.get("x-csrf-token", "").encode("latin1"),
                    self.sessions.csrf(cookie).encode("ascii"),
                ):
                    raise AppError(403, "csrf_denied", "A valid session CSRF token is required.")
            upload = method == "POST" and path == "/api/captures"
            limit = (
                self.settings.max_upload_bytes
                if upload
                else 512 * 1024
                if method == "POST" and path == "/api/speech/transcribe"
                else 352 * 1024
                if method == "POST" and path == "/api/turns"
                else 64 * 1024
            )
            length = headers.get("content-length")
            if length is not None:
                try:
                    if not length.isdecimal():
                        raise ValueError("Invalid length")
                    if int(length) > limit:
                        raise AppError(
                            413, "body_limit", "Request body exceeds the endpoint size limit."
                        )
                except ValueError as exc:
                    raise AppError(
                        400, "invalid_length", "Content-Length must be a nonnegative integer."
                    ) from exc
            body = bytearray()
            async with asyncio.timeout(15):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        raise AppError(
                            413, "body_limit", "Request body exceeds the endpoint size limit."
                        )
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
            if length is not None and int(length) != len(body):
                raise AppError(
                    400, "length_mismatch", "Request body length does not match Content-Length."
                )
            if body and not upload:
                if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                    raise AppError(415, "json_required", "Use application/json for this operation.")
                try:
                    value = strict_json(bytes(body))
                    if not isinstance(value, dict):
                        raise ValueError("Expected object")
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise AppError(
                        422,
                        "invalid_json",
                        "Body must be a JSON object with distinct keys and finite values.",
                    ) from exc
            sent = False

            async def replay() -> Message:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, secure_send)
        except AppError as exc:
            await JSONResponse(exc.payload(), status_code=exc.status)(scope, receive, secure_send)
        except TimeoutError:
            await JSONResponse(
                AppError(408, "upload_timeout", "Request body timed out; retry.").payload(),
                status_code=408,
            )(scope, receive, secure_send)
