"""Offline-only, explicitly confirmed POI imports and ephemeral location queries.

Wire ``app.state.poi = POICache(app.state.repo.db)`` and include ``router``.
The shared database lock serializes cache replacement and delete-all. The existing
fresh-database deletion path recreates the migrated POI tables with zero records.
This module never fetches maps, acquires GPS, calls a model, or stores query fixes.
"""

import json
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from app.database import Database
from app.errors import AppError
from app.poi_contracts import (
    CACHE_STALE_SECONDS,
    MAX_FIX_AGE_SECONDS,
    MAX_IMPORT_BYTES,
    MAX_POIS,
    CacheClear,
    CacheImport,
    CoverageBounds,
    NearestRequest,
    POIElement,
    parse_timestamp,
)

router = APIRouter(prefix="/api/poi", tags=["offline POI cache"])

SHOP_CATEGORIES = {
    "supermarket": "supermarket",
    "grocery": "grocery",
    "convenience": "convenience",
    "hardware": "hardware",
    "doityourself": "hardware",
    "clothes": "clothes",
    "shoes": "shoes",
    "bicycle": "bicycle",
    "electronics": "electronics",
    "chemist": "pharmacy",
}
AMENITY_CATEGORIES = {
    category: category
    for category in (
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
    )
}


def category_for(element: POIElement) -> str:
    category = AMENITY_CATEGORIES.get(element.tags.get("amenity", "")) or (
        SHOP_CATEGORIES.get(element.tags.get("shop", ""))
    )
    if category is None:
        raise AppError(
            422,
            "unsupported_poi_category",
            "Every imported record must have a supported shop or amenity tag.",
        )
    return category


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Finite great-circle distance, stable at poles and antipodal points."""
    values = (lat1, lon1, lat2, lon2)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in values
    ):
        raise ValueError("Coordinates must be finite numbers")
    if not (
        -90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180
    ):
        raise ValueError("Coordinates outside range")
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = phi2 - phi1
    delta_lon = math.radians(lon2 - lon1)
    value = math.sin(delta_phi / 2) ** 2 + (
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lon / 2) ** 2
    )
    value = min(1.0, max(0.0, value))
    return 6_371_008.8 * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class POICache:
    def __init__(self, db: Database, clock: Callable[[], float] = time.time) -> None:
        self.db, self.clock = db, clock

    def initialize(self) -> None:
        """Verify migrations were applied by the owning repository startup."""
        with self.db.lock, self.db.connect() as conn:
            conn.execute("SELECT singleton FROM poi_cache_meta LIMIT 1")
            conn.execute("SELECT namespace FROM poi_cache_entries LIMIT 1")

    @staticmethod
    def clear(conn: Any) -> None:
        """Optional hook for an owning deletion transaction; does not change generation."""
        conn.execute("DELETE FROM poi_cache_entries")
        conn.execute("DELETE FROM poi_cache_meta")

    def _expected(self, conn: Any, expected: int) -> None:
        actual = self.db.generation(conn)
        if actual != expected:
            raise AppError(
                409,
                "generation_conflict",
                "Local data changed. Review it before replacing the cache.",
                current_generation=actual,
            )

    def _status(self, conn: Any, now: float) -> dict[str, Any]:
        meta = conn.execute("SELECT * FROM poi_cache_meta WHERE singleton=1").fetchone()
        count = conn.execute("SELECT count(*) FROM poi_cache_entries").fetchone()[0]
        age = max(0.0, now - meta["imported_epoch"]) if meta else None
        provenance = json.loads(meta["provenance"]) if meta and meta["provenance"] else None
        return {
            "download_provenance": provenance,
            "generation": self.db.generation(conn),
            "record_count": count,
            "dataset_label": meta["dataset_label"] if meta else None,
            "source": provenance["source"]
            if provenance
            else ("user_confirmed_offline_import" if meta else None),
            "imported_at": meta["imported_at"] if meta else None,
            "fetched_at": provenance["fetched_at"] if provenance else None,
            "source_observed_at": meta["source_observed_at"] if meta else None,
            "source_observed_at_verified": False,
            "source_freshness": "unknown",
            "attribution": {
                "text": "© OpenStreetMap contributors",
                "url": "https://www.openstreetmap.org/copyright",
                "license": "ODbL",
                "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
                "source_note": "Downloaded from the public OSM Overpass source; availability and completeness unverified."
                if provenance
                else "User-supplied OSM-format records; provenance has not been verified.",
            },
            "import_age_seconds": age,
            "cache_freshness": "empty"
            if not meta
            else (
                "import_stale"
                if age is not None and age > CACHE_STALE_SECONDS
                else "recently_imported"
            ),
            "coverage_bounds": json.loads(meta["coverage_bounds"]) if meta else None,
            "coverage_complete": False,
            "coverage_status": "incomplete" if meta else "no_cache",
            "offline": True,
            "network_fetch_performed": provenance is not None,
            "location_queries_persisted": False,
            "stock_verified": False,
            "opening_hours_verified": False,
            "route_verified": False,
            "limits": {
                "records": MAX_POIS,
                "import_bytes": MAX_IMPORT_BYTES,
                "fix_max_age_seconds": MAX_FIX_AGE_SECONDS,
                "fix_max_accuracy_m": 1000,
            },
        }

    def status(self) -> dict[str, Any]:
        with self.db.lock, self.db.connect() as conn:
            return self._status(conn, self.clock())

    def replace(
        self,
        body: CacheImport,
        *,
        provenance: dict[str, Any] | None = None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> dict[str, Any]:
        encoded = body.model_dump_json().encode("utf-8")
        if len(encoded) > MAX_IMPORT_BYTES:
            raise AppError(413, "poi_import_limit", "POI import exceeds the cache byte limit.")
        # Validate every record before touching the previous snapshot.
        rows = []
        for element in body.elements:
            category = category_for(element)
            name = element.tags.get("name", "").strip() or (
                f"Unnamed {category.replace('_', ' ')} ({element.type}/{element.id})"
            )
            point = element.coordinates
            tags = json.dumps(
                element.tags, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            rows.append((element.type, element.id, category, name, tags, point.lat, point.lon))
        now = self.clock()
        imported_at = datetime.fromtimestamp(now, UTC).isoformat()
        bounds = body.coverage_bounds.model_dump_json()
        with self.db.lock, self.db.connect(write=True) as conn:
            self._expected(conn, body.expected_generation)
            if cancelled():
                raise AppError(409, "request_cancelled", "Area download cancelled before saving.")
            self.clear(conn)
            conn.executemany("INSERT INTO poi_cache_entries VALUES (?,?,?,?,?,?,?)", rows)
            conn.execute(
                "INSERT INTO poi_cache_meta VALUES (1,?,?,?,?,?,?)",
                (
                    body.dataset_label,
                    imported_at,
                    now,
                    body.source_observed_at,
                    bounds,
                    json.dumps(provenance) if provenance else None,
                ),
            )
            self.db.changed(conn)
            return self._status(conn, now)

    def delete(self, body: CacheClear) -> dict[str, Any]:
        with self.db.lock, self.db.connect(write=True) as conn:
            self._expected(conn, body.expected_generation)
            self.clear(conn)
            self.db.changed(conn)
            return {"deleted": True, **self._status(conn, self.clock())}

    def nearest(self, body: NearestRequest) -> dict[str, Any]:
        now = self.clock()
        age = now - parse_timestamp(body.location.captured_at).timestamp()
        if age < -5 or age > MAX_FIX_AGE_SECONDS:
            raise AppError(
                422,
                "stale_location_fix",
                "Supply a recent location fix with a valid timestamp.",
                max_age_seconds=MAX_FIX_AGE_SECONDS,
            )
        with self.db.lock, self.db.connect() as conn:
            cache = self._status(conn, now)
            matches = []
            for row in conn.execute(
                "SELECT * FROM poi_cache_entries WHERE category=?", (body.category,)
            ):
                distance = haversine_m(body.location.lat, body.location.lon, row["lat"], row["lon"])
                if distance <= body.max_distance_m:
                    matches.append(
                        {
                            "namespace": row["namespace"],
                            "osm_id": row["osm_id"],
                            "key": f"{row['namespace']}/{row['osm_id']}",
                            "name": row["name"],
                            "category": row["category"],
                            "lat": row["lat"],
                            "lon": row["lon"],
                            "tags": json.loads(row["tags"]),
                            "distance_m": round(distance, 2),
                            "representative_point": row["namespace"] != "node",
                            "_distance": distance,
                        }
                    )
            matches.sort(key=lambda row: (row["_distance"], row["namespace"], row["osm_id"]))
            total = len(matches)
            results = matches[: body.limit]
            for row in results:
                row.pop("_distance")
            bounds = cache["coverage_bounds"]
            within = (
                CoverageBounds.model_validate(bounds).contains(body.location.lat, body.location.lon)
                if bounds is not None
                else False
            )
            return {
                "kind": "cached_matches" if total else "no_cached_matches",
                "results": results,
                "total_cached_matches": total,
                "cache": cache,
                "distance_kind": "straight_line_to_cached_point",
                "nearest_scope": "matching_records_in_the_imported_cache_only",
                "location_fix_age_seconds": max(0.0, age),
                "location_accuracy_m": body.location.accuracy_m,
                "within_declared_bounds": within,
                "coverage_complete": False,
                "live_location_verified": False,
                "stock_verified": False,
                "opening_hours_verified": False,
                "route_verified": False,
                "empty_result_meaning": "No matching cached records; nearby places may be missing.",
            }


@router.get("/cache")
def cache_status(request: Request) -> dict[str, Any]:
    return request.app.state.poi.status()


@router.put("/cache")
def import_cache(body: CacheImport, request: Request) -> dict[str, Any]:
    return request.app.state.poi.replace(body)


@router.delete("/cache")
def clear_cache(body: CacheClear, request: Request) -> dict[str, Any]:
    return request.app.state.poi.delete(body)


@router.post("/nearest")
def nearest(body: NearestRequest, request: Request) -> dict[str, Any]:
    return request.app.state.poi.nearest(body)
