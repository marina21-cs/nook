import asyncio
import sqlite3
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.actions import Actions
from app.actions import router as actions_router
from app.api import router
from app.audio_service import AudioService
from app.audio_service import router as audio_router
from app.capture_service import CaptureService
from app.chat_context import ChatContexts
from app.config import Settings
from app.conversation import router as conversation_router
from app.errors import AppError
from app.evidence_store import EvidenceStore
from app.frontend import router as frontend_router
from app.inference.text import TextAdapter
from app.inference.vision import VisionAdapter
from app.item_repository import ItemRepository
from app.language import render_recall, render_spoken_recall
from app.local_chat import LocalChatProvider
from app.local_voice import LocalVoice
from app.poi import POICache
from app.poi import router as poi_router
from app.poi_download import AreaDownloader
from app.poi_download import router as download_router
from app.recall_service import RecallService
from app.requests import RequestRegistry
from app.security import BoundaryMiddleware, Sessions
from app.turn_service import TurnService
from app.turn_service import router as turn_router


class LocalAPI(FastAPI):
    openapi_factory: Callable[[], dict[str, Any]] | None = None

    def openapi(self) -> dict[str, Any]:
        if self.openapi_factory is not None:
            return self.openapi_factory()
        return super().openapi()


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings.from_env()
    sessions = Sessions()

    @asynccontextmanager
    async def lifespan(api: FastAPI) -> AsyncIterator[None]:
        store = EvidenceStore(configuration)
        api.state.store = store
        try:
            api.state.settings = configuration
            api.state.sessions = sessions
            api.state.repo = ItemRepository(configuration, store)
            api.state.actions = Actions(api.state.repo)
            api.state.captures = CaptureService(api.state.repo)
            api.state.poi = POICache(api.state.repo.db)
            api.state.poi.initialize()
            api.state.area_downloader = AreaDownloader(configuration.poi_download_enabled)
            api.state.text = TextAdapter(configuration)
            api.state.vision = VisionAdapter(configuration)
            api.state.recall = RecallService(api.state.repo, api.state.text)
            api.state.requests = RequestRegistry()
            api.state.chat_contexts = ChatContexts()
            api.state.chat_provider = LocalChatProvider(configuration)
            api.state.repo.db.on_changed = api.state.chat_contexts.clear
            api.state.chat_expiry = (
                asyncio.create_task(api.state.chat_contexts.expire())
                if configuration.chat_enabled
                else None
            )
            api.state.voice = LocalVoice() if configuration.voice_enabled else None
            api.state.turns = TurnService(
                api.state.repo,
                store,
                api.state.recall,
                api.state.vision,
                api.state.requests,
                speech_to_text=api.state.voice,
                text_to_speech=api.state.voice,
                reply_renderer=lambda result, language: render_recall(
                    result.model_dump(), language
                ),
                speech_renderer=lambda result, language: render_spoken_recall(
                    result.model_dump(), language
                ),
                provider_timeout=30.0
                if configuration.voice_enabled
                else configuration.model_timeout,
            )
            api.state.audio = AudioService(api.state.turns, speech_to_text=api.state.voice)
            yield
        finally:
            if hasattr(api.state, "requests"):
                api.state.requests.cancel_target()
            if hasattr(api.state, "chat_contexts"):
                api.state.chat_contexts.clear()
            if getattr(api.state, "chat_expiry", None) is not None:
                api.state.chat_expiry.cancel()
                await asyncio.gather(api.state.chat_expiry, return_exceptions=True)
            if hasattr(api.state, "chat_provider"):
                await api.state.chat_provider.close()
            if getattr(api.state, "voice", None) is not None:
                await api.state.voice.close()
            store.close()

    # Built-in Swagger/ReDoc fetch CDN assets, so serve only local machine-readable OpenAPI.
    api = LocalAPI(
        title="appbuilderhck local visual memory",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        responses={
            400: {"description": "Malformed request"},
            401: {"description": "Session required"},
            403: {"description": "Origin/host/CSRF rejected"},
            409: {"description": "Revision/idempotency/generation conflict"},
            422: {"description": "Validation failed"},
            503: {"description": "Local storage/inference unavailable"},
        },
    )
    api.add_middleware(BoundaryMiddleware, settings=configuration, sessions=sessions)
    api.include_router(router)
    api.include_router(conversation_router)
    api.include_router(actions_router)
    api.include_router(turn_router)
    api.include_router(audio_router)
    api.include_router(poi_router)
    api.include_router(download_router)
    api.include_router(frontend_router)

    def schema() -> dict:
        if api.openapi_schema:
            return api.openapi_schema
        document = get_openapi(title=api.title, version=api.version, routes=api.routes)
        components = document.setdefault("components", {})
        components["securitySchemes"] = {
            "LocalSessionCookie": {"type": "apiKey", "in": "cookie", "name": "app_session"},
            "CsrfToken": {"type": "apiKey", "in": "header", "name": "X-CSRF-Token"},
        }
        components.setdefault("schemas", {})["ErrorEnvelope"] = {
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {
                    "type": "object",
                    "required": ["code", "message", "details"],
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "details": {"type": "object", "additionalProperties": True},
                    },
                }
            },
        }
        for path, operations in document["paths"].items():
            for method, operation in operations.items():
                if method not in {"get", "post", "patch", "delete", "put", "head", "options"}:
                    continue
                protected = path not in {"/api/session", "/api/status"}
                security: dict[str, list] = {"LocalSessionCookie": []} if protected else {}
                if protected and method not in {"get", "head", "options"}:
                    security["CsrfToken"] = []
                operation["security"] = [security] if security else []
                for code, response in operation["responses"].items():
                    if code.isdigit() and int(code) >= 400:
                        response["content"] = {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                            }
                        }
                if path == "/api/captures" and method == "post":
                    operation["requestBody"] = {
                        "required": True,
                        "content": {
                            media: {"schema": {"type": "string", "format": "binary"}}
                            for media in ("image/jpeg", "image/png", "image/webp")
                        },
                    }
                if path.startswith("/api/photos/") or path.endswith("/photo"):
                    operation["responses"]["200"]["content"] = {
                        "image/jpeg": {"schema": {"type": "string", "format": "binary"}}
                    }
        api.openapi_schema = document
        return document

    api.openapi_factory = schema

    @api.exception_handler(AppError)
    async def domain_error(request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(error.payload(), status_code=error.status)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(map(str, e["loc"])),
                "code": e["type"],
                "message": "Invalid field value",
            }
            for e in error.errors()
        ]
        return JSONResponse(
            AppError(422, "validation_error", "Check the request fields.", fields=fields).payload(),
            status_code=422,
        )

    @api.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            AppError(
                error.status_code, "http_error", "Endpoint or method is unavailable."
            ).payload(),
            status_code=error.status_code,
        )

    @api.exception_handler(OSError)
    @api.exception_handler(sqlite3.Error)
    async def storage_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            AppError(
                503,
                "storage_unavailable",
                "Local storage operation failed. Reload before retrying; use the same idempotency key.",
            ).payload(),
            status_code=503,
        )

    return api


app = create_app()
