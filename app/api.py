import asyncio
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.contracts import (
    AddObservation,
    CaptureView,
    Commit,
    CommitResult,
    DeleteData,
    DeleteItem,
    Edit,
    ItemList,
    ItemView,
    ManualCreate,
    Recall,
    RecallResult,
    Suggest,
    SuggestResult,
)
from app.errors import AppError
from app.recall_service import matches

router = APIRouter(prefix="/api")


@router.get("/session")
def session(request: Request) -> JSONResponse:
    cookie, token = request.app.state.sessions.issue()
    response = JSONResponse({"csrf_token": token, "expires_in_seconds": 3600})
    response.set_cookie(
        "app_session", cookie, max_age=3600, httponly=True, samesite="strict", path="/"
    )
    return response


@router.get("/status")
async def status(request: Request) -> dict:
    state = request.app.state

    def snapshot() -> tuple[int, int, int, int]:
        with state.repo.db.lock, state.repo.db.connect() as conn:
            generation = state.repo.db.generation(conn)
            write_epoch = state.repo.write_epoch(conn)
            count = conn.execute("SELECT count(*) FROM items").fetchone()[0]
            schema = conn.execute("PRAGMA user_version").fetchone()[0]
        return generation, write_epoch, count, schema

    generation, write_epoch, count, schema = await asyncio.to_thread(snapshot)
    return {
        "status": "ready",
        "backend_version": "0.1.0",
        "schema_version": schema,
        "execution_device": "local laptop",
        "serving_boundary": "loopback only; one OS user",
        "generation": generation,
        "write_epoch": write_epoch,
        "item_count": count,
        "vision": state.vision.status(),
        "text": await state.text.status(),
        "chat": state.chat_provider.status(),
        "cloud_dependency": False,
        "queries_persisted": False,
        "actions": {
            "engine": "bounded_deterministic",
            "approval_required": True,
            "ttl_seconds": 300,
        },
        "turns": state.turns.status(),
        "speech": {
            "input_contract_available": True,
            "transcript_requires_explicit_confirmation": True,
            "provider_enabled": state.voice is not None,
            "artifacts_present": state.voice.provisioned() if state.voice else False,
            "real_inference_accepted": False,
            "tts_language": "en",
            "automatic_downloads": False,
        },
        "poi": {
            "available": True,
            "mode": "confirmed area download/import and offline straight-line query",
            "download_enabled": request.app.state.settings.poi_download_enabled,
            "network_fetch_performed": False,
            "location_queries_persisted": False,
            "coverage_complete": False,
        },
        "language": {
            "mode": "literal labels with bounded English/Filipino recall wrappers",
            "translation_available": False,
            "general_taglish_verified": False,
        },
        "visual_retrieval": {"available": False, "reason": "model_export_calibration_pending"},
        "limits": {
            "upload_bytes": state.settings.max_upload_bytes,
            "decoded_pixels": state.settings.max_pixels,
            "evidence_bytes": state.settings.max_evidence_bytes,
            "evidence_max_edge": state.settings.evidence_edge,
            "items": state.settings.max_items,
            "rows_per_capture": 5,
            "drafts": state.settings.max_drafts,
            "observations_per_item": 100,
        },
    }


@router.post("/captures", response_model=CaptureView, status_code=201)
async def upload(request: Request, source: Literal["camera", "import"] = "import") -> Any:
    body = await request.body()
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    return await asyncio.to_thread(request.app.state.captures.create, body, media_type, source)


@router.get("/captures/{capture_id}", response_model=CaptureView)
def get_capture(capture_id: UUID, request: Request) -> Any:
    return request.app.state.captures.get(str(capture_id))


@router.get("/captures/{capture_id}/photo")
def draft_photo(capture_id: UUID, request: Request) -> Response:
    state = request.app.state
    with state.repo.db.lock, state.repo.db.connect() as conn:
        state.captures.get_row(conn, str(capture_id))
        data = state.store.read(str(capture_id), draft=True)
        return Response(data, media_type="image/jpeg")


@router.post("/captures/{capture_id}/suggest", response_model=SuggestResult)
async def suggest(capture_id: UUID, body: Suggest, request: Request) -> dict:
    state = request.app.state
    async with state.requests.begin(str(body.request_id), str(capture_id)) as cancelled:

        def snapshot() -> tuple[int, bytes]:
            with state.repo.db.lock, state.repo.db.connect() as conn:
                state.captures.get_row(conn, str(capture_id))
                generation = state.repo.db.generation(conn)
                encoded = state.store.read(str(capture_id), draft=True)
            return generation, encoded

        generation, encoded = await asyncio.to_thread(snapshot)
        candidates, elapsed = await state.vision.suggest(encoded, cancelled)
        if cancelled.is_set():
            raise AppError(
                409, "request_cancelled", "Photo check cancelled; its result was discarded."
            )
        draft = await asyncio.to_thread(
            state.captures.candidates, str(capture_id), candidates, generation
        )
        return {
            "request_id": str(body.request_id),
            "candidates": draft["candidates"],
            "inference_used": True,
            "elapsed_ms": elapsed,
            "draft_saved_items": 0,
            "identity_verified": False,
            "location_verified": False,
            "inventory_complete": False,
            "manual_confirmation_required": True,
        }


@router.post("/captures/{capture_id}/commit", response_model=CommitResult)
def commit(capture_id: UUID, body: Commit, request: Request) -> Any:
    return request.app.state.captures.commit(str(capture_id), body)


@router.delete("/captures/{capture_id}")
async def discard(capture_id: UUID, request: Request) -> dict:
    state = request.app.state
    state.requests.cancel_target(str(capture_id))
    return await asyncio.to_thread(state.captures.discard, str(capture_id))


@router.get("/items", response_model=ItemList)
def items(
    request: Request,
    query: Annotated[str | None, Query(max_length=2000)] = None,
    offset: Annotated[int, Query(ge=0, le=200)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    repo = request.app.state.repo
    with repo.db.lock, repo.db.connect() as conn:
        results = repo.all(conn)
        if query is not None:
            results = matches(results, query)
        return {
            "items": results[offset : offset + limit],
            "total": len(results),
            "offset": offset,
            "limit": limit,
            "generation": repo.db.generation(conn),
        }


@router.post("/items", response_model=CommitResult, status_code=201)
def manual(body: ManualCreate, request: Request) -> Any:
    return request.app.state.repo.create_manual(body)


@router.get("/items/{item_id}", response_model=ItemView)
def get_item(item_id: UUID, request: Request) -> Any:
    return request.app.state.repo.get(str(item_id))


@router.patch("/items/{item_id}", response_model=CommitResult)
def edit(item_id: UUID, body: Edit, request: Request) -> Any:
    return request.app.state.repo.edit(str(item_id), body)


@router.post("/items/{item_id}/observations", response_model=CommitResult)
def observe(item_id: UUID, body: AddObservation, request: Request) -> Any:
    return request.app.state.repo.add_observation(str(item_id), body)


@router.get("/items/{item_id}/deletion-preview")
def deletion_preview(item_id: UUID, request: Request) -> Any:
    return request.app.state.repo.deletion_preview(str(item_id))


@router.delete("/items/{item_id}")
async def delete(item_id: UUID, body: DeleteItem, request: Request) -> dict:
    state = request.app.state
    pending = [stop for stop, _ in state.requests.active.values()]
    result = await asyncio.to_thread(state.repo.delete, str(item_id), body)
    if not result["replayed"]:
        state.actions.clear()
        for stop in pending:
            stop.set()
    return result


@router.delete("/data")
async def delete_all(body: DeleteData, request: Request) -> dict:
    state = request.app.state
    pending = [stop for stop, _ in state.requests.active.values()]
    result = await asyncio.to_thread(state.repo.delete_all, body)
    if not result["replayed"]:
        state.actions.clear()
        for stop in pending:
            stop.set()
    return result


@router.post("/recall", response_model=RecallResult)
async def recall(body: Recall, request: Request) -> Any:
    state = request.app.state
    async with state.requests.begin(str(body.request_id)) as cancelled:
        generation = await asyncio.to_thread(state.repo.generation)
        return await state.recall.recall(body, cancelled, generation)


@router.post("/requests/{request_id}/cancel")
async def cancel(request_id: UUID, request: Request) -> dict:
    return request.app.state.requests.cancel(str(request_id), request.state.session_owner)


@router.get("/photos/{photo_id}")
def photo(photo_id: UUID, request: Request) -> Response:
    state = request.app.state
    with state.repo.db.lock, state.repo.db.connect() as conn:
        exists = conn.execute("SELECT 1 FROM photos WHERE id=?", (str(photo_id),)).fetchone()
        if not exists:
            raise AppError(404, "evidence_unavailable", "Photo evidence is unavailable.")
        return Response(state.store.read(str(photo_id)), media_type="image/jpeg")
