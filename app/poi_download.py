"""Explicit, bounded public-area retrieval; no GPS, background sync, or cloud AI."""

import asyncio
import hashlib
import math
import time
from datetime import UTC, datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Request
from pydantic import Field, ValidationError, field_validator

from app.contracts import ApiUUID, strict_json
from app.errors import AppError
from app.poi import AMENITY_CATEGORIES, SHOP_CATEGORIES
from app.poi_contracts import CacheImport, Coordinates, CoverageBounds, Label, POIConfirmed

ENDPOINT = "https://overpass-api.de/api/interpreter"
MAX_DOWNLOAD_BYTES = 1024 * 1024
COOLDOWN_SECONDS = 30
router = APIRouter(prefix="/api/poi", tags=["explicit online area download"])


class AreaDownload(POIConfirmed):
    request_id: ApiUUID
    expected_generation: int = Field(ge=0)
    consent_to_share_area: Literal[True]
    label: Label
    center: Coordinates
    radius_m: int = Field(ge=100, le=1000)

    @field_validator("consent_to_share_area", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        return POIConfirmed.literal_confirmation(value)


def area_bounds(body: AreaDownload) -> CoverageBounds:
    lat, lon = body.center.lat, body.center.lon
    if abs(lat) > 85:
        raise AppError(422, "area_unsupported", "Choose an area between 85° south and north.")
    dy = body.radius_m / 111_000
    dx = dy / math.cos(math.radians(lat))
    if lon - dx < -180 or lon + dx > 180:
        raise AppError(422, "area_unsupported", "Choose an area away from the date line.")
    return CoverageBounds(south=lat - dy, north=lat + dy, west=lon - dx, east=lon + dx)


def query_for(bounds: CoverageBounds) -> str:
    box = ",".join(f"{v:.7f}" for v in (bounds.south, bounds.west, bounds.north, bounds.east))
    amenity = "|".join(sorted(AMENITY_CATEGORIES))
    shops = "|".join(sorted(SHOP_CATEGORIES))
    return f'[out:json][timeout:15][maxsize:8388608];(nwr["amenity"~"^({amenity})$"]({box});nwr["shop"~"^({shops})$"]({box}););out center 251;'


def snapshot(raw: bytes, body: AreaDownload, bounds: CoverageBounds) -> CacheImport:
    try:
        data = strict_json(raw)
        if (
            not isinstance(data, dict)
            or data.get("remark")
            or not isinstance(data.get("elements"), list)
        ):
            raise ValueError("Incomplete response")
        if len(data["elements"]) > 250:
            raise AppError(
                413,
                "area_too_dense",
                "More than 250 places were returned. Choose a smaller area; the old cache is unchanged.",
            )
        elements = []
        for value in data["elements"]:
            if not isinstance(value, dict):
                raise ValueError("Invalid place")
            kind = value.get("type")
            point = (
                {"lat": value.get("lat"), "lon": value.get("lon")}
                if kind == "node"
                else value.get("center")
            )
            coord = Coordinates.model_validate(point)
            # A way/relation can intersect the box while its center falls outside it.
            if not bounds.contains(coord.lat, coord.lon):
                continue
            tags = value.get("tags")
            if not isinstance(tags, dict):
                raise ValueError("Missing tags")
            retained = {
                k: v
                for k, v in tags.items()
                if k in {"name", "amenity", "shop", "addr:street", "addr:housenumber", "addr:city"}
            }
            elements.append(
                {
                    "type": kind,
                    "id": value.get("id"),
                    "tags": retained,
                    **(coord.model_dump() if kind == "node" else {"center": coord.model_dump()}),
                }
            )
        if not elements:
            raise AppError(
                404,
                "area_no_places",
                "No supported cached points were found in that area. Previous cache unchanged.",
            )
        timestamp = data.get("osm3s", {}).get("timestamp_osm_base")
        return CacheImport.model_validate(
            {
                "confirmed": True,
                "expected_generation": body.expected_generation,
                "dataset_label": body.label,
                "snapshot_complete": True,
                "element_count": len(elements),
                "coverage_bounds": bounds.model_dump(),
                "source_observed_at": timestamp,
                "elements": elements,
            }
        )
    except AppError:
        raise
    except (ValueError, TypeError, AttributeError, RecursionError, ValidationError) as exc:
        raise AppError(
            502,
            "area_invalid_response",
            "The source returned incomplete or unsupported data. Previous cache unchanged.",
        ) from exc


class AreaDownloader:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.active = False
        self.last_attempt = float("-inf")

    async def fetch(self, query: str) -> bytes:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5), follow_redirects=False, trust_env=False
        ) as client:
            async with client.stream(
                "POST",
                ENDPOINT,
                data={"data": query},
                headers={
                    "User-Agent": "Nook-local-prototype/0.1 (explicit bounded area cache)",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                if response.status_code in {429, 503, 504}:
                    raise AppError(
                        503,
                        "area_source_busy",
                        "The public map source is busy. Wait at least 30 seconds before trying again; your old cache remains available.",
                    )
                if response.status_code != 200 or response.headers.get(
                    "content-encoding", "identity"
                ) not in {"identity", ""}:
                    raise AppError(
                        502,
                        "area_source_failed",
                        "The public map download failed. Your old cache remains available.",
                    )
                length = response.headers.get("content-length")
                if length is not None and (
                    not length.isdigit() or int(length) > MAX_DOWNLOAD_BYTES
                ):
                    raise AppError(
                        413,
                        "area_download_limit",
                        "Source response exceeds the bounded download limit. Choose a smaller area.",
                    )
                raw = bytearray()
                async for chunk in response.aiter_raw(chunk_size=16384):
                    if len(raw) + len(chunk) > MAX_DOWNLOAD_BYTES:
                        raise AppError(
                            413,
                            "area_download_limit",
                            "Download exceeded 1 MiB. Choose a smaller area; previous cache unchanged.",
                        )
                    raw.extend(chunk)
                return bytes(raw)

    async def run(self, body: AreaDownload, request: Request) -> dict:
        if not self.enabled:
            raise AppError(
                503,
                "area_download_disabled",
                "Online area downloads have not been enabled by the local operator. Existing offline cache remains usable.",
            )
        bounds = area_bounds(body)
        if self.active:
            raise AppError(409, "area_download_busy", "One area download is already running.")
        if time.monotonic() - self.last_attempt < COOLDOWN_SECONDS:
            raise AppError(
                429, "area_download_cooldown", "Wait 30 seconds between area download attempts."
            )
        async with request.app.state.requests.begin(str(body.request_id)) as cancelled:
            self.active = True
            self.last_attempt = time.monotonic()
            task = asyncio.create_task(self.fetch(query_for(bounds)))
            stop = asyncio.create_task(cancelled.wait())
            try:
                done, _ = await asyncio.wait(
                    {task, stop}, timeout=22, return_when=asyncio.FIRST_COMPLETED
                )
                if cancelled.is_set():
                    raise AppError(
                        409,
                        "request_cancelled",
                        "Area download cancelled. No new snapshot was saved.",
                    )
                if task not in done:
                    raise AppError(
                        504,
                        "area_download_timeout",
                        "Area download timed out. The previous cache remains available.",
                    )
                raw = task.result()
                body_import = snapshot(raw, body, bounds)
                provenance = {
                    "source": "osm_overpass_download",
                    "url": ENDPOINT,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "download_bytes": len(raw),
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                }
                result = await asyncio.to_thread(
                    request.app.state.poi.replace,
                    body_import,
                    provenance=provenance,
                    cancelled=cancelled.is_set,
                )
                return {
                    "saved": True,
                    "cache": result,
                    "download_bytes": len(raw),
                    "wifi_verified": False,
                }
            except httpx.HTTPError as exc:
                raise AppError(
                    503,
                    "area_network_unavailable",
                    "Could not reach the public source. Use the previously saved area offline, or retry later.",
                ) from exc
            finally:
                task.cancel()
                stop.cancel()
                await asyncio.gather(task, stop, return_exceptions=True)
                self.active = False


@router.post("/download")
async def download_area(body: AreaDownload, request: Request) -> dict:
    return await request.app.state.area_downloader.run(body, request)
