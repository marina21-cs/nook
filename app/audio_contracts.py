"""Strict, ephemeral inputs for review-before-recall spoken turns."""

import base64
import binascii
import struct
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.contracts import ApiUUID, Contract, Query

MAX_AUDIO_SECONDS = 10
MAX_AUDIO_BYTES = 320044
MAX_AUDIO_BASE64 = 4 * ((MAX_AUDIO_BYTES + 2) // 3)
AudioLanguage = Literal["en", "tl", "auto"]


@dataclass(frozen=True)
class ValidatedAudio:
    data: bytes
    duration_seconds: float


def validate_wav(data: bytes) -> ValidatedAudio:
    """Accept only canonical RIFF PCM16 mono 16 kHz; never open a file or decoder.

    Requiring the standard fmt/data layout rejects metadata, duplicate chunks,
    trailing payloads and ambiguous/truncated container lengths before inference.
    """
    if not 46 <= len(data) <= MAX_AUDIO_BYTES:
        raise ValueError("Audio must be a nonempty WAV of at most 10 seconds")
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Audio must be RIFF WAVE")
    if struct.unpack_from("<I", data, 4)[0] != len(data) - 8:
        raise ValueError("WAV length is invalid")
    if data[12:16] != b"fmt " or data[36:40] != b"data":
        raise ValueError("Only the canonical PCM WAV layout is accepted")
    fmt_size, encoding, channels, rate, byte_rate, alignment, bits = struct.unpack_from(
        "<IHHIIHH", data, 16
    )
    if (fmt_size, encoding, channels, rate, byte_rate, alignment, bits) != (
        16,
        1,
        1,
        16000,
        32000,
        2,
        16,
    ):
        raise ValueError("Audio must be mono 16 kHz PCM16 WAV")
    size = struct.unpack_from("<I", data, 40)[0]
    if size != len(data) - 44 or size % 2 or not 0 < size <= 320000:
        raise ValueError("WAV sample data length is invalid")
    # Centered energy rejects silence, tiny quantization noise, and constant DC.
    # This is an input quality floor, not a claim to detect human speech.
    count = size // 2
    total = squares = 0
    for (sample,) in struct.iter_unpack("<h", memoryview(data)[44:]):
        total += sample
        squares += sample * sample
    if squares * count - total * total < 32 * 32 * count * count:
        raise ValueError("Audio is silent or too quiet; record again or type the text")
    return ValidatedAudio(data, count / 16000)


class AudioInput(Contract):
    content_type: Literal["audio/wav"]
    data_base64: Annotated[str, StringConstraints(min_length=4, max_length=MAX_AUDIO_BASE64)]

    @model_validator(mode="after")
    def bounded_audio(self) -> "AudioInput":
        self.decode()
        return self

    def decode(self) -> bytes:
        try:
            data = base64.b64decode(self.data_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Audio must contain plain valid base64") from exc
        if not data or len(data) > MAX_AUDIO_BYTES:
            raise ValueError("Audio exceeds the decoded size limit")
        return data


class Transcribe(Contract):
    request_id: ApiUUID
    audio: AudioInput
    language_hint: AudioLanguage = "auto"


class SpokenTurn(Contract):
    request_id: ApiUUID
    utterance: Query
    transcript_confirmed: Literal[True]

    @field_validator("transcript_confirmed", mode="before")
    @classmethod
    def explicit_review(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("Explicit boolean true transcript confirmation is required")
        return value


class TranscriptResult(Contract):
    request_id: ApiUUID
    transcript: Query
    transcript_confirmed: Literal[False] = False
    editable: Literal[True] = True
    persisted: Literal[False] = False
    provider: Annotated[str, StringConstraints(min_length=1, max_length=160)] | None = None
    language_hint: AudioLanguage
    language: Annotated[str, StringConstraints(min_length=2, max_length=16)] | None = None
    duration_seconds: float = Field(gt=0, le=MAX_AUDIO_SECONDS)
    elapsed_ms: float = Field(ge=0)
    generation: int = Field(ge=0)
