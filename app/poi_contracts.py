"""Strict, bounded contracts for explicitly imported offline map records."""

import math
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.contracts import Contract

MAX_POIS = 250
MAX_IMPORT_BYTES = 64 * 1024
MAX_FIX_AGE_SECONDS = 120
MAX_ACCURACY_METERS = 1000
CACHE_STALE_SECONDS = 7 * 24 * 3600

Category = Literal[
    "supermarket",
    "grocery",
    "convenience",
    "hardware",
    "clothes",
    "shoes",
    "bicycle",
    "electronics",
    "pharmacy",
    "clinic",
    "hospital",
    "cafe",
    "restaurant",
    "fuel",
    "bank",
    "atm",
    "drinking_water",
    "toilets",
]
Namespace = Literal["node", "way", "relation"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
TagKey = Annotated[str, StringConstraints(min_length=1, max_length=64)]
TagValue = Annotated[str, StringConstraints(max_length=240)]


def parse_timestamp(value: str) -> datetime:
    """Timezone required: a local wall clock cannot establish fix age."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Use an ISO 8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed


class Coordinates(Contract):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    @field_validator("lat", "lon", mode="before")
    @classmethod
    def numeric_coordinate(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Coordinates must be finite numbers")
        if not math.isfinite(value):
            raise ValueError("Coordinates must be finite numbers")
        return value


class CoverageBounds(Contract):
    south: float = Field(ge=-90, le=90)
    north: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    east: float = Field(ge=-180, le=180)

    @field_validator("south", "north", "west", "east", mode="before")
    @classmethod
    def numeric_bounds(cls, value: Any) -> Any:
        return Coordinates.numeric_coordinate(value)

    @model_validator(mode="after")
    def ordered_latitudes(self) -> "CoverageBounds":
        if self.south > self.north:
            raise ValueError("South must not exceed north")
        return self

    def contains(self, lat: float, lon: float) -> bool:
        longitude = (
            self.west <= lon <= self.east
            if self.west <= self.east
            else (lon >= self.west or lon <= self.east)
        )
        return self.south <= lat <= self.north and longitude


class POIElement(Contract):
    type: Namespace
    id: int = Field(ge=1, le=2**63 - 1)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    center: Coordinates | None = None
    tags: dict[TagKey, TagValue] = Field(min_length=1, max_length=24)

    @field_validator("lat", "lon", mode="before")
    @classmethod
    def numeric_optional(cls, value: Any) -> Any:
        return None if value is None else Coordinates.numeric_coordinate(value)

    @field_validator("tags")
    @classmethod
    def safe_tags(cls, value: dict[str, str]) -> dict[str, str]:
        if any(
            any(ord(c) < 32 or ord(c) == 127 for c in part)
            for pair in value.items()
            for part in pair
        ):
            raise ValueError("Control characters are not allowed in tags")
        return value

    @model_validator(mode="after")
    def representative_coordinate(self) -> "POIElement":
        if self.type == "node":
            if self.lat is None or self.lon is None or self.center is not None:
                raise ValueError("Nodes require lat/lon and cannot provide center")
        elif self.center is None or self.lat is not None or self.lon is not None:
            raise ValueError("Ways and relations require a representative center")
        return self

    @property
    def coordinates(self) -> Coordinates:
        if self.center is not None:
            return self.center
        if self.lat is None or self.lon is None:
            raise ValueError("Missing representative coordinate")
        return Coordinates(lat=self.lat, lon=self.lon)


class POIConfirmed(Contract):
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def literal_confirmation(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("Explicit boolean true confirmation is required")
        return value


class CacheImport(POIConfirmed):
    expected_generation: int = Field(ge=0)
    dataset_label: Label
    # This confirms the supplied file finished; it never claims complete map coverage.
    snapshot_complete: Literal[True]
    element_count: int = Field(ge=1, le=MAX_POIS)
    coverage_bounds: CoverageBounds
    source_observed_at: str | None = Field(default=None, max_length=40)
    elements: list[POIElement] = Field(min_length=1, max_length=MAX_POIS)

    @field_validator("snapshot_complete", mode="before")
    @classmethod
    def literal_snapshot(cls, value: Any) -> Any:
        return POIConfirmed.literal_confirmation(value)

    @field_validator("source_observed_at")
    @classmethod
    def source_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            parse_timestamp(value)
        return value

    @model_validator(mode="after")
    def full_snapshot(self) -> "CacheImport":
        if self.element_count != len(self.elements):
            raise ValueError("Declared element count does not match the complete supplied file")
        keys = [(element.type, element.id) for element in self.elements]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate namespace/id")
        for element in self.elements:
            point = element.coordinates
            if not self.coverage_bounds.contains(point.lat, point.lon):
                raise ValueError("Record lies outside the declared bounds")
        return self


class CacheClear(POIConfirmed):
    expected_generation: int = Field(ge=0)


class LocationFix(Coordinates):
    captured_at: str = Field(min_length=1, max_length=40)
    accuracy_m: float = Field(gt=0, le=MAX_ACCURACY_METERS)

    @field_validator("accuracy_m", mode="before")
    @classmethod
    def numeric_accuracy(cls, value: Any) -> Any:
        return Coordinates.numeric_coordinate(value)

    @field_validator("captured_at")
    @classmethod
    def fix_timestamp(cls, value: str) -> str:
        parse_timestamp(value)
        return value


class NearestRequest(POIConfirmed):
    location: LocationFix
    category: Category
    max_distance_m: float = Field(default=5000, gt=0, le=100_000)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("max_distance_m", mode="before")
    @classmethod
    def numeric_radius(cls, value: Any) -> Any:
        return Coordinates.numeric_coordinate(value)
