"""Replaceable speech boundaries. No provider, credentials or downloads are provisioned."""

import asyncio
from dataclasses import dataclass
from typing import Literal, Protocol


class SpeechUnavailable(Exception):
    """A provisioned speech provider cannot currently serve a request."""


@dataclass(frozen=True)
class RenderedSpeech:
    data: bytes
    content_type: Literal["audio/wav", "audio/mpeg", "audio/ogg"]
    duration_seconds: float


class SpeechToText(Protocol):
    """Future adapters must bound input and release it on cancellation; never persist it."""

    async def transcribe(
        self, audio: bytes, cancellation: asyncio.Event, *, language_hint: str = "auto"
    ) -> str: ...


class TextToSpeech(Protocol):
    """Adapters must honor task cancellation and never save or execute their inputs."""

    async def render(self, text: str, cancellation: asyncio.Event) -> RenderedSpeech: ...


class UnavailableSpeechToText:
    async def transcribe(
        self, audio: bytes, cancellation: asyncio.Event, *, language_hint: str = "auto"
    ) -> str:
        raise SpeechUnavailable("Speech recognition is not provisioned; type one utterance.")


class UnavailableTextToSpeech:
    async def render(self, text: str, cancellation: asyncio.Event) -> RenderedSpeech:
        raise SpeechUnavailable("Speech rendering is not provisioned; read the text response.")
