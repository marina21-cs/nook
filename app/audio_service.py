"""Two-step spoken recall: ephemeral transcription, then explicit reviewed text."""

import asyncio
import math
import time
from collections.abc import Awaitable
from typing import Any, TypeVar

from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.audio_contracts import SpokenTurn, Transcribe, TranscriptResult, validate_wav
from app.errors import AppError
from app.speech import SpeechToText, SpeechUnavailable, UnavailableSpeechToText
from app.turn_contracts import Turn, TurnResult
from app.turn_service import TurnService

router = APIRouter(prefix="/api/speech")
T = TypeVar("T")


class AudioService:
    def __init__(
        self,
        turns: TurnService,
        *,
        speech_to_text: SpeechToText | None = None,
        provider_timeout: float | None = None,
    ) -> None:
        self.turns = turns
        self.speech_to_text = speech_to_text or UnavailableSpeechToText()
        self.provider_timeout = (
            turns.provider_timeout if provider_timeout is None else provider_timeout
        )
        if not math.isfinite(self.provider_timeout) or not 0 < self.provider_timeout <= 30:
            raise ValueError("Provider timeout must be positive and at most 30 seconds")

    async def bounded(self, work: Awaitable[T], cancelled: asyncio.Event) -> T:
        task = asyncio.ensure_future(work)
        stop = asyncio.create_task(cancelled.wait())
        try:
            done, _ = await asyncio.wait(
                {task, stop}, timeout=self.provider_timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if cancelled.is_set():
                raise AppError(
                    409, "request_cancelled", "Transcription cancelled; result discarded."
                )
            if task not in done:
                raise TimeoutError("Speech provider deadline exceeded")
            return task.result()
        finally:
            task.cancel()
            stop.cancel()

            def observe(finished: asyncio.Future[Any]) -> None:
                if not finished.cancelled():
                    finished.exception()

            task.add_done_callback(observe)
            stop.add_done_callback(observe)
            await asyncio.sleep(0)

    async def transcribe(self, body: Transcribe) -> TranscriptResult:
        started = time.monotonic()
        async with self.turns.requests.begin(str(body.request_id)) as cancelled:
            generation = await asyncio.to_thread(self.turns.repo.generation)
            await self.turns.check(cancelled, generation)
            try:
                audio = validate_wav(body.audio.decode())
            except ValueError as exc:
                raise AppError(
                    422,
                    "invalid_audio",
                    "Supply audible mono 16 kHz PCM16 WAV, at most 10 seconds.",
                ) from exc
            try:
                transcript = await self.bounded(
                    self.speech_to_text.transcribe(
                        audio.data, cancelled, language_hint=body.language_hint
                    ),
                    cancelled,
                )
            except SpeechUnavailable as exc:
                raise AppError(
                    503, "speech_unavailable", "Local transcription is unavailable. Type your text."
                ) from exc
            except TimeoutError as exc:
                raise AppError(
                    504,
                    "speech_timeout",
                    "Transcription timed out. Record again or type your text.",
                ) from exc
            except AppError as exc:
                if exc.code in {"request_cancelled", "stale_request", "speech_busy"}:
                    raise
                raise AppError(
                    503, "speech_failed", "Transcription failed. Record again or type your text."
                ) from exc
            except Exception as exc:
                raise AppError(
                    503, "speech_failed", "Transcription failed. Record again or type your text."
                ) from exc
            await self.turns.check(cancelled, generation)
            try:
                result = TranscriptResult(
                    request_id=body.request_id,
                    transcript=transcript,
                    provider=getattr(self.speech_to_text, "provider_name", None),
                    language_hint=body.language_hint,
                    duration_seconds=audio.duration_seconds,
                    elapsed_ms=round((time.monotonic() - started) * 1000, 2),
                    generation=generation,
                )
            except (ValidationError, TypeError, ValueError) as exc:
                raise AppError(
                    502,
                    "invalid_transcript",
                    "No usable transcript was returned. Record again or type your text.",
                ) from exc
            await self.turns.check(cancelled, generation)
            return result

    async def run(self, body: SpokenTurn) -> TurnResult:
        # No transcript cache, lookup, model intent routing, or mutation authority.
        # The second step accepts the user's current edited text under a fresh ID.
        return await self.turns.run(
            Turn(
                request_id=body.request_id,
                utterance=body.utterance,
                intent="recall",
                language="en",
                use_recall_inference=False,
                render_speech=True,
            )
        )


@router.post("/transcribe", response_model=TranscriptResult)
async def transcribe(body: Transcribe, request: Request) -> TranscriptResult:
    return await request.app.state.audio.transcribe(body)


@router.post("/turns", response_model=TurnResult)
async def spoken_turn(body: SpokenTurn, request: Request) -> TurnResult:
    return await request.app.state.audio.run(body)
