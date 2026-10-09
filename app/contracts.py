import json
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)]
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ApiUUID = Annotated[UUID, Field(strict=False)]


def strict_json(raw: str | bytes) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in values:
            if k in result:
                raise ValueError("Duplicate JSON key")
            result[k] = v
        return result

    def constant(value: str) -> Any:
        raise ValueError("Non-finite JSON value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @field_validator("*", mode="after")
    @classmethod
    def no_controls(cls, value: Any) -> Any:
        if isinstance(value, str) and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Control characters are not allowed")
        return value


class Region(Contract):
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside(self) -> "Region":
        if self.x + self.w > 1.000000001 or self.y + self.h > 1.000000001:
            raise ValueError("Region must be inside the normalized evidence image")
        return self


class NamedFields(Contract):
    personal_name: Name
    aliases: list[Name] = Field(default_factory=list, max_length=10)
    distinguishing_note: Note = ""
    category: Name | None = None  # User-reviewed metadata; separate from candidates.

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, values: list[str]) -> list[str]:
        if len({v.casefold() for v in values}) != len(values):
            raise ValueError("Aliases must be distinct")
        if any(any(ord(c) < 32 or ord(c) == 127 for c in v) for v in values):
            raise ValueError("Alias contains a control character")
        return values


class ReviewedRow(NamedFields):
    identity: Literal["new", "existing"]
    item_id: ApiUUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    region: Region | None = None
    candidate_id: ApiUUID | None = None

    @model_validator(mode="after")
    def explicit_identity(self) -> "ReviewedRow":
        if self.identity == "existing":
            if self.item_id is None or self.expected_revision is None:
                raise ValueError("Existing items require item_id and expected_revision")
        elif self.item_id is not None or self.expected_revision is not None:
            raise ValueError("New items cannot specify item_id or expected_revision")
        return self


class Confirmed(Contract):
    confirmed: Literal[True]
    idempotency_key: ApiUUID
    write_epoch: int = Field(default=0, ge=0)

    @field_validator("confirmed", mode="before")
    @classmethod
    def literal_confirmation(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("Explicit boolean true confirmation is required")
        return value


class Commit(Confirmed):
    rows: list[ReviewedRow] = Field(min_length=1, max_length=5)
    location: Location
    make_current: bool = False
    review_after_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def distinct_existing(self) -> "Commit":
        ids = [r.item_id for r in self.rows if r.item_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("An existing item can appear only once per commit")
        return self


class ManualCreate(Confirmed, NamedFields):
    location: Location | None
    review_after_days: int | None = Field(default=None, ge=1, le=3650)


class Edit(Confirmed):
    expected_revision: int = Field(ge=1)
    personal_name: Name | None = None
    aliases: list[Name] | None = Field(default=None, max_length=10)
    distinguishing_note: Note | None = None
    category: Name | None = None

    @model_validator(mode="after")
    def has_edit(self) -> "Edit":
        if not self.model_fields_set & {
            "personal_name",
            "aliases",
            "distinguishing_note",
            "category",
        }:
            raise ValueError("At least one metadata field is required")
        if any(
            getattr(self, key) is None
            for key in self.model_fields_set & {"personal_name", "aliases", "distinguishing_note"}
        ):
            raise ValueError("Name, aliases and note cannot be null")
        if self.aliases is not None:
            NamedFields(personal_name="validation", aliases=self.aliases)
        return self


class AddObservation(Confirmed):
    expected_revision: int = Field(ge=1)
    location: Location | None  # null explicitly marks moved/unknown.
    review_after_days: int | None = Field(default=None, ge=1, le=3650)


class DeleteItem(Confirmed):
    expected_revision: int = Field(ge=1)
    evidence_scope: Literal["unreferenced", "all_affected"]


class DeleteData(Confirmed):
    confirmation: Literal["DELETE ALL LOCAL DATA"]
    expected_generation: int = Field(ge=0)


class Recall(Contract):
    query: Query
    request_id: ApiUUID
    use_inference: bool = False


class Suggest(Contract):
    request_id: ApiUUID


class Normalization(Contract):
    intent: Literal["recall"]
    terms: list[Name] = Field(min_length=1, max_length=3)


class Candidate(Contract):
    id: ApiUUID
    category: Name
    score: float = Field(ge=0, le=1)
    region: Region
    model: str
    model_digest: str


class PhotoView(BaseModel):
    id: str
    width: int
    height: int
    sha256: str
    source: str
    captured_at: str | None
    recorded_at: str
    metadata_stripped: bool
    available: bool
    url: str


class ObservationView(BaseModel):
    id: str
    location: str | None
    location_state: str
    confirmed_at: str
    observed_at: str | None
    provenance: str
    review_after: str | None
    region: dict[str, float] | None
    candidate_provenance: dict[str, Any] | None
    evidence_status: str
    photo: PhotoView | None


class ItemView(BaseModel):
    id: str
    revision: int
    personal_name: str
    aliases: list[str]
    distinguishing_note: str
    category: str | None
    created_at: str
    updated_at: str
    current_observation: ObservationView | None
    observations: list[ObservationView]
    freshness: str
    location: str | None
    location_label: Literal["Last recorded", "Location unknown"]
    live_location_verified: Literal[False] = False


class CaptureView(BaseModel):
    id: str
    width: int
    height: int
    source: str
    captured_at: str | None
    recorded_at: str
    metadata_stripped: bool
    photo_url: str
    candidates: list[Candidate]
    saved_items: Literal[0] = 0


class SuggestResult(BaseModel):
    request_id: str
    candidates: list[Candidate]
    inference_used: Literal[True] = True
    elapsed_ms: float
    draft_saved_items: Literal[0] = 0
    identity_verified: Literal[False] = False
    location_verified: Literal[False] = False
    inventory_complete: Literal[False] = False
    manual_confirmation_required: Literal[True] = True


class ItemList(BaseModel):
    items: list[ItemView]
    total: int
    offset: int
    limit: int
    generation: int


class CommitResult(BaseModel):
    items: list[ItemView]
    replayed: bool
    generation: int
    write_epoch: int


class RecallResult(BaseModel):
    kind: Literal["found", "clarify", "unknown"]
    request_id: str
    items: list[ItemView]
    total: int
    generation: int
    reason: str
    inference_used: bool
    fallback_used: bool
    inference_status: str
    repair_used: bool = False
    elapsed_ms: float
