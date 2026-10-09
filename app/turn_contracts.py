"""Strict, bounded ephemeral turn data; saving belongs to the capture API."""

import base64
import binascii
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.contracts import ApiUUID, Candidate, Contract, Query, RecallResult

MAX_FRAME_BYTES = 256 * 1024
MAX_FRAME_BASE64 = 4 * ((MAX_FRAME_BYTES + 2) // 3)
MAX_SPEECH_BYTES = 30 * 24000 * 2 + 44
MAX_SPEECH_BASE64 = 4 * ((MAX_SPEECH_BYTES + 2) // 3)
Language = Literal["en", "fil", "auto"]
TurnKind = Literal["memory", "candidate", "clarify", "unknown", "unsupported"]
SpeechStatus = Literal[
    "not_provisioned",
    "not_requested",
    "rendered",
    "unavailable",
    "timeout",
    "failed",
    "invalid_output",
]


class TurnFrame(Contract):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    data_base64: Annotated[str, StringConstraints(min_length=4, max_length=MAX_FRAME_BASE64)]

    @model_validator(mode="after")
    def bounded_image(self) -> "TurnFrame":
        self.decode()
        return self

    def decode(self) -> bytes:
        try:
            data = base64.b64decode(self.data_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Frame must contain plain, valid base64") from exc
        if not data or len(data) > MAX_FRAME_BYTES:
            raise ValueError("Frame must be nonempty and at most 256 KiB")
        return data


class Turn(Contract):
    request_id: ApiUUID
    utterance: Query
    intent: Literal["recall", "category", "visual_question"] = "recall"
    language: Language = "auto"
    frame: TurnFrame | None = None
    use_vision: bool = False
    use_recall_inference: bool = False
    render_speech: bool = False

    @model_validator(mode="after")
    def explicit_inference(self) -> "Turn":
        if self.use_vision and self.frame is None:
            raise ValueError("Vision requires one deliberately supplied frame")
        if self.use_vision and self.intent != "category":
            raise ValueError("Vision is only available for category suggestions")
        if self.use_recall_inference and self.intent != "recall":
            raise ValueError("Recall inference requires recall intent")
        return self


class TurnFrameInfo(Contract):
    width: int = Field(ge=1, le=2048)
    height: int = Field(ge=1, le=2048)
    metadata_stripped: Literal[True] = True
    persisted: Literal[False] = False


class TurnInference(Contract):
    vision_used: bool = False
    vision_status: Literal[
        "not_requested", "completed", "unavailable", "timeout", "failed", "invalid_output"
    ] = "not_requested"
    recall_used: bool = False
    identity_verified: Literal[False] = False
    location_verified: Literal[False] = False
    visual_conversation_supported: Literal[False] = False


class TurnSpeech(Contract):
    available: bool = False
    status: SpeechStatus = "not_provisioned"
    content_type: Literal["audio/wav", "audio/mpeg", "audio/ogg"] | None = None
    audio_base64: Annotated[str, StringConstraints(max_length=MAX_SPEECH_BASE64)] | None = None
    duration_seconds: float | None = Field(default=None, gt=0, le=30)
    spoken_text: Annotated[str, StringConstraints(max_length=4000)] | None = None


class TurnResult(Contract):
    turn_id: ApiUUID
    kind: TurnKind
    reply_text: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    language: Language
    candidates: list[Candidate] = Field(default_factory=list, max_length=20)
    recall: RecallResult | None = None
    frame: TurnFrameInfo | None = None
    inference: TurnInference
    speech: TurnSpeech
    generation: int = Field(ge=0)
    persisted: Literal[False] = False
    manual_confirmation_required: Literal[True] = True
    elapsed_ms: float = Field(ge=0)
