"""One bounded, ephemeral turn with no mutation or model-directed tool authority."""

import asyncio
import base64
import math
import sqlite3
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from fastapi import APIRouter, Request

from app.contracts import Candidate, Recall, RecallResult
from app.errors import AppError
from app.evidence_store import EvidenceStore
from app.item_repository import ItemRepository
from app.recall_service import RecallService
from app.requests import RequestRegistry
from app.speech import (
    RenderedSpeech,
    SpeechToText,
    SpeechUnavailable,
    TextToSpeech,
    UnavailableSpeechToText,
    UnavailableTextToSpeech,
)
from app.turn_contracts import (
    MAX_SPEECH_BYTES,
    Language,
    SpeechStatus,
    Turn,
    TurnFrameInfo,
    TurnInference,
    TurnKind,
    TurnResult,
    TurnSpeech,
)

T = TypeVar("T")
router = APIRouter(prefix="/api")


class CategoryDetector(Protocol):
    async def suggest(
        self, encoded: bytes, cancelled: asyncio.Event
    ) -> tuple[list[Candidate], float]: ...


def recall_reply(result: RecallResult, language: Language) -> str:
    """Application-owned baseline; localized wrappers can be injected by the host."""
    if result.kind == "clarify":
        return "Several confirmed records match. Choose the personal record you mean."
    if not result.items:
        return "I do not have a confirmed matching record."
    item = result.items[0]
    if item.location is None:
        return f"The recorded location of {item.personal_name} is unknown."
    observation = item.current_observation
    date = observation.confirmed_at if observation else "an unknown date"
    reply = f"{item.personal_name}: last recorded at {item.location}, confirmed {date}."
    if item.freshness != "last_recorded":
        reply += " Review the record's freshness before relying on it."
    return reply + " This is recorded memory; the current location is unverified."


class TurnService:
    def __init__(
        self,
        repository: ItemRepository,
        store: EvidenceStore,
        recall: RecallService,
        vision: CategoryDetector,
        requests: RequestRegistry,
        *,
        speech_to_text: SpeechToText | None = None,
        text_to_speech: TextToSpeech | None = None,
        reply_renderer: Callable[[RecallResult, Language], str] | None = None,
        speech_renderer: Callable[[RecallResult, Language], str] | None = None,
        provider_timeout: float = 15.0,
    ) -> None:
        if not math.isfinite(provider_timeout) or not 0 < provider_timeout <= 30:
            raise ValueError("Provider timeout must be positive and at most 30 seconds")
        self.repo, self.store, self.recall = repository, store, recall
        self.vision, self.requests = vision, requests
        self.speech_to_text = speech_to_text or UnavailableSpeechToText()
        self.text_to_speech = text_to_speech or UnavailableTextToSpeech()
        self.reply_renderer = reply_renderer or recall_reply
        self.speech_renderer = speech_renderer
        self.provider_timeout = provider_timeout

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "input": "one typed utterance and optional deliberately supplied still frame",
            "ephemeral_by_default": True,
            "audio_input_supported": False,
            "speech_to_text_available": False,
            "text_to_speech_available": not isinstance(
                self.text_to_speech, UnavailableTextToSpeech
            ),
            "visual_conversation_supported": False,
            "saving_requires_separate_capture_confirmation": True,
            "cloud_dependency": (
                False if isinstance(self.text_to_speech, UnavailableTextToSpeech) else None
            ),
            "downloads_automatic": False,
        }

    async def check(self, cancelled: asyncio.Event, generation: int) -> None:
        if cancelled.is_set():
            raise AppError(409, "request_cancelled", "Turn cancelled; its result was discarded.")
        if await asyncio.to_thread(self.repo.generation) != generation:
            raise AppError(
                409, "stale_request", "Collection changed during the turn. Use a new request ID."
            )
        if cancelled.is_set():
            raise AppError(409, "request_cancelled", "Turn cancelled; its result was discarded.")

    async def bounded(self, work: Awaitable[T], cancelled: asyncio.Event) -> T:
        """Race providers against Stop and a deadline; cancel late work immediately."""
        task = asyncio.ensure_future(work)
        stop = asyncio.create_task(cancelled.wait())
        try:
            done, _ = await asyncio.wait(
                {task, stop}, timeout=self.provider_timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if cancelled.is_set():
                raise AppError(409, "request_cancelled", "Turn cancelled; result discarded.")
            if task not in done:
                raise TimeoutError("Turn provider deadline exceeded")
            return task.result()
        finally:
            task.cancel()
            stop.cancel()

            # Protocol implementations must honor task cancellation. Observe failures without
            # delaying the response if a broken provider refuses cancellation.
            def observe(finished: asyncio.Future[Any]) -> None:
                if not finished.cancelled():
                    finished.exception()

            task.add_done_callback(observe)
            stop.add_done_callback(observe)
            await asyncio.sleep(0)  # Let cancellation-aware adapters release their inputs.

    async def run(self, body: Turn) -> TurnResult:
        start = time.monotonic()
        async with self.requests.begin(str(body.request_id)) as cancelled:
            generation = await asyncio.to_thread(self.repo.generation)
            await self.check(cancelled, generation)
            frame = None
            encoded = None
            if body.frame:
                # sanitize only; never create/finalize a capture or write evidence bytes.
                encoded, width, height, _ = await asyncio.to_thread(
                    self.store.sanitize, body.frame.decode(), body.frame.content_type
                )
                frame = TurnFrameInfo(width=width, height=height)
                await self.check(cancelled, generation)
            inference = TurnInference()
            candidates: list[Candidate] = []
            memory = None
            kind: TurnKind
            if body.intent == "recall":
                recall_request = Recall(
                    query=body.utterance,
                    request_id=body.request_id,
                    use_inference=body.use_recall_inference,
                )
                try:
                    raw = await self.bounded(
                        self.recall.recall(recall_request, cancelled, generation), cancelled
                    )
                except (OSError, sqlite3.Error):
                    raise
                except Exception as exc:
                    if isinstance(exc, AppError) and exc.status == 409:
                        raise
                    if not body.use_recall_inference:
                        raise
                    await self.check(cancelled, generation)
                    raw = await self.recall.recall(
                        recall_request.model_copy(update={"use_inference": False}),
                        cancelled,
                        generation,
                    )
                    raw.update(
                        inference_used=False,
                        fallback_used=True,
                        inference_status="timeout" if isinstance(exc, TimeoutError) else "failed",
                    )
                memory = RecallResult.model_validate(raw)
                inference.recall_used = memory.inference_used
                kind = "memory" if memory.kind == "found" else memory.kind
                reply = self.reply_renderer(memory, body.language)
            elif body.intent == "visual_question":
                kind = "unsupported"
                reply = (
                    "General visual conversation is unavailable. I can offer limited category "
                    "suggestions for a deliberately supplied frame or recall confirmed records."
                )
            elif not body.use_vision:
                kind = "unknown"
                reply = "Photo analysis was not requested. Enter a category manually or explicitly request suggestions."
            else:
                try:
                    assert encoded is not None  # Enforced by the Turn contract.
                    raw_candidates, _ = await self.bounded(
                        self.vision.suggest(encoded, cancelled), cancelled
                    )
                    if not isinstance(raw_candidates, list) or len(raw_candidates) > 20:
                        raise ValueError("Invalid candidate count")
                    validated = [
                        Candidate.model_validate(c.model_dump() if isinstance(c, Candidate) else c)
                        for c in raw_candidates
                    ]
                    if len({candidate.id for candidate in validated}) != len(validated):
                        raise ValueError("Duplicate candidate identifiers")
                    if any(
                        not 1 <= len(candidate.model) <= 160
                        or len(candidate.model_digest) != 64
                        or any(c not in "0123456789abcdef" for c in candidate.model_digest)
                        for candidate in validated
                    ):
                        raise ValueError("Invalid bounded candidate provenance")
                    candidates = validated
                    inference.vision_used = True
                    inference.vision_status = "completed"
                except AppError as exc:
                    if exc.code == "request_cancelled":
                        raise
                    if exc.status == 504:
                        inference.vision_status = "timeout"
                    elif exc.code == "invalid_vision_output":
                        inference.vision_status = "invalid_output"
                    elif exc.code == "vision_failed":
                        inference.vision_status = "failed"
                    else:
                        inference.vision_status = "unavailable"
                except TimeoutError:
                    inference.vision_status = "timeout"
                except (ValueError, TypeError):
                    inference.vision_status = "invalid_output"
                except Exception:
                    inference.vision_status = "failed"
                kind = "candidate" if candidates else "unknown"
                reply = (
                    "These are tentative category suggestions. Choose or enter a category manually; "
                    "a category cannot identify your personal item or its location."
                    if candidates
                    else "No reliable category suggestion is available. Review the frame and enter a category manually."
                )
            # Validate app-owned text before handing it to any speech adapter.
            response = TurnResult(
                turn_id=body.request_id,
                kind=kind,
                reply_text=reply,
                language=body.language,
                candidates=candidates,
                recall=memory,
                frame=frame,
                inference=inference,
                speech=TurnSpeech(),
                generation=generation,
                elapsed_ms=round((time.monotonic() - start) * 1000, 2),
            )
            await self.check(cancelled, generation)
            if body.render_speech:
                spoken = (
                    self.speech_renderer(memory, body.language)
                    if memory is not None and self.speech_renderer
                    else response.reply_text
                )
                response.speech = await self.render(spoken, cancelled)
            elif not isinstance(self.text_to_speech, UnavailableTextToSpeech):
                response.speech = TurnSpeech(available=True, status="not_requested")
            await self.check(
                cancelled, generation
            )  # Discard late output after any record mutation.
            response.elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            return response

    async def render(self, text: str, cancelled: asyncio.Event) -> TurnSpeech:
        status: SpeechStatus
        try:
            output = await self.bounded(self.text_to_speech.render(text, cancelled), cancelled)
            if (
                not isinstance(output, RenderedSpeech)
                or not isinstance(output.data, bytes)
                or not 0 < len(output.data) <= MAX_SPEECH_BYTES
                or output.content_type not in {"audio/wav", "audio/mpeg", "audio/ogg"}
                or isinstance(output.duration_seconds, bool)
                or not math.isfinite(output.duration_seconds)
                or not 0 < output.duration_seconds <= 30
            ):
                raise ValueError("Invalid rendered speech")
            return TurnSpeech(
                available=True,
                status="rendered",
                content_type=output.content_type,
                audio_base64=base64.b64encode(output.data).decode("ascii"),
                duration_seconds=output.duration_seconds,
                spoken_text=text,
            )
        except SpeechUnavailable:
            status = (
                "not_provisioned"
                if isinstance(self.text_to_speech, UnavailableTextToSpeech)
                else "unavailable"
            )
        except AppError as exc:
            if exc.code == "request_cancelled":
                raise
            status = "failed"
        except TimeoutError:
            status = "timeout"
        except (ValueError, TypeError):
            status = "invalid_output"
        except Exception:
            status = "failed"
        return TurnSpeech(status=status)


@router.post("/turns", response_model=TurnResult)
async def turn(body: Turn, request: Request) -> TurnResult:
    return await request.app.state.turns.run(body)
