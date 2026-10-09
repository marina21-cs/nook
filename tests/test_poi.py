"""Synthetic POI records only; inherited fixture forbids outbound connections."""

import json
import math
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.database import Database
from app.errors import AppError
from app.poi import POICache, haversine_m
from app.poi_contracts import (
    MAX_IMPORT_BYTES,
    MAX_POIS,
    CacheClear,
    CacheImport,
    Coordinates,
    NearestRequest,
)

NOW = 1_800_000_000.0


def timestamp(offset=0):
    return datetime.fromtimestamp(NOW + offset, UTC).isoformat()


def element(osm_id=1, namespace="node", lat=0.0, lon=0.0, **tags):
    return {
        "type": namespace,
        "id": osm_id,
        **(
            {"lat": lat, "lon": lon}
            if namespace == "node"
            else {"center": {"lat": lat, "lon": lon}}
        ),
        "tags": {"amenity": "pharmacy", **tags},
    }


def import_body(records=None, **overrides):
    records = records if records is not None else [element()]
    return {
        "confirmed": True,
        "expected_generation": 0,
        "dataset_label": "Synthetic test map",
        "snapshot_complete": True,
        "element_count": len(records),
        "coverage_bounds": {"south": -90.0, "north": 90.0, "west": -180.0, "east": 180.0},
        "elements": records,
        **overrides,
    }


def query_body(**overrides):
    return {
        "confirmed": True,
        "location": {"lat": 0.0, "lon": 0.0, "captured_at": timestamp(), "accuracy_m": 20.0},
        "category": "pharmacy",
        **overrides,
    }


@pytest.fixture
def cache(tmp_path):
    db = Database(tmp_path / "synthetic.sqlite")
    db.migrate()
    cache = POICache(db, clock=lambda: NOW)
    cache.initialize()
    return cache


@pytest.mark.parametrize(
    "value", [True, False, "1.0", None, float("nan"), float("inf"), -float("inf")]
)
@pytest.mark.parametrize("field", ["lat", "lon"])
def test_coordinate_strict_finite(field, value):
    with pytest.raises(ValidationError):
        Coordinates.model_validate({"lat": 0.0, "lon": 0.0, field: value})


@pytest.mark.parametrize("coordinates", [(91, 0), (0, 181), (-91, 0), (0, -181)])
def test_coordinate_ranges(coordinates):
    with pytest.raises(ValidationError):
        Coordinates(lat=coordinates[0], lon=coordinates[1])


def test_haversine_antimeridian_poles_and_antipodes():
    assert haversine_m(0, 179.9, 0, -179.9) == pytest.approx(22_239.016, abs=0.01)
    assert haversine_m(90, -180, 90, 180) < 1e-6
    assert haversine_m(90, 0, -90, 0) == pytest.approx(math.pi * 6_371_008.8)
    assert haversine_m(12, 34, 12, 34) == 0
    for bad in [True, "0", float("nan"), float("inf"), 91]:
        with pytest.raises(ValueError):
            haversine_m(bad, 0, 0, 0)


def test_namespaces_fallback_and_no_live_claims(cache):
    body = CacheImport.model_validate(
        import_body(
            [
                element(1, "node", name="Synthetic Alpha", opening_hours="24/7"),
                element(1, "way"),
                element(1, "relation"),
            ],
            source_observed_at=timestamp(-86400),
        )
    )
    status = cache.replace(body)
    assert status["generation"] == 1
    assert status["record_count"] == 3
    assert status["source"] == "user_confirmed_offline_import"
    assert status["fetched_at"] is None
    assert status["source_observed_at_verified"] is False
    result = cache.nearest(NearestRequest.model_validate(query_body()))
    assert {row["key"] for row in result["results"]} == {"node/1", "way/1", "relation/1"}
    assert any(row["name"] == "Unnamed pharmacy (way/1)" for row in result["results"])
    node = next(row for row in result["results"] if row["key"] == "node/1")
    assert node["tags"]["opening_hours"] == "24/7"
    assert status["attribution"]["url"] == "https://www.openstreetmap.org/copyright"
    assert result["distance_kind"] == "straight_line_to_cached_point"
    for field in [
        "coverage_complete",
        "live_location_verified",
        "stock_verified",
        "opening_hours_verified",
        "route_verified",
    ]:
        assert result[field] is False
    assert result["cache"]["source_freshness"] == "unknown"


@pytest.mark.parametrize(
    "changed",
    [
        {"snapshot_complete": False},
        {"snapshot_complete": 1},
        {"confirmed": 1},
        {"element_count": 2},
        {"elements": []},
        {"elements": [element(), element()]},
        {"elements": [element(osm_id=True)]},
        {"elements": [element(namespace="way") | {"lat": 0.0}]},
        {"elements": [element() | {"center": {"lat": 0.0, "lon": 0.0}}]},
        {"elements": [element() | {"tags": {"amenity": "pharmacy", "name": "Bad\x00Name"}}]},
        {"coverage_bounds": {"south": 1.0, "north": 2.0, "west": 1.0, "east": 2.0}},
        {"source_observed_at": "2026-10-01T12:00:00"},
    ],
)
def test_malformed_or_incomplete_replacement_preserves_cache(cache, changed):
    cache.replace(CacheImport.model_validate(import_body()))
    with pytest.raises(ValidationError):
        CacheImport.model_validate(import_body(expected_generation=1, **changed))
    assert cache.status()["record_count"] == 1
    assert cache.status()["generation"] == 1


def test_unsupported_records_do_not_partially_replace(cache):
    cache.replace(CacheImport.model_validate(import_body()))
    body = CacheImport.model_validate(
        import_body(
            [
                element(2),
                element(3) | {"tags": {"amenity": "unsupported"}},
            ],
            expected_generation=1,
        )
    )
    with pytest.raises(AppError, match="unsupported_poi_category"):
        cache.replace(body)
    result = cache.nearest(NearestRequest.model_validate(query_body()))
    assert [row["key"] for row in result["results"]] == ["node/1"]
    assert cache.status()["generation"] == 1


def test_transaction_failure_preserves_previous_snapshot(cache):
    cache.replace(CacheImport.model_validate(import_body()))
    with cache.db.connect() as conn:
        conn.execute("""CREATE TRIGGER synthetic_failure BEFORE INSERT ON poi_cache_entries
                        WHEN NEW.osm_id=9 BEGIN SELECT RAISE(ABORT, 'test rollback'); END""")
    body = CacheImport.model_validate(import_body([element(2), element(9)], expected_generation=1))
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        cache.replace(body)
    result = cache.nearest(NearestRequest.model_validate(query_body()))
    assert [row["key"] for row in result["results"]] == ["node/1"]
    assert cache.status()["generation"] == 1


def test_count_and_bytes_are_bounded(cache):
    with pytest.raises(ValidationError):
        CacheImport.model_validate(import_body([element(i + 1) for i in range(MAX_POIS + 1)]))
    records = [element(i + 1, name="Synthetic " + "X" * 220) for i in range(MAX_POIS)]
    body = CacheImport.model_validate(import_body(records))
    assert len(body.model_dump_json().encode()) > MAX_IMPORT_BYTES
    with pytest.raises(AppError, match="poi_import_limit"):
        cache.replace(body)
    assert cache.status()["record_count"] == 0


def test_generation_guard_and_clear(cache):
    cache.replace(CacheImport.model_validate(import_body()))
    with pytest.raises(AppError, match="generation_conflict"):
        cache.replace(CacheImport.model_validate(import_body()))
    with pytest.raises(AppError, match="generation_conflict"):
        cache.delete(CacheClear(confirmed=True, expected_generation=0))
    result = cache.delete(CacheClear(confirmed=True, expected_generation=1))
    assert result["record_count"] == 0 and result["generation"] == 2
    assert result["coverage_status"] == "no_cache"


@pytest.mark.parametrize("offset", [-121, 6])
def test_stale_future_location_rejected(cache, offset):
    query = query_body()
    query["location"]["captured_at"] = timestamp(offset)
    with pytest.raises(AppError, match="stale_location_fix"):
        cache.nearest(NearestRequest.model_validate(query))


@pytest.mark.parametrize("accuracy", [0, 1001, True, "5", float("nan"), float("inf")])
def test_invalid_accuracy_rejected(accuracy):
    query = query_body()
    query["location"]["accuracy_m"] = accuracy
    with pytest.raises(ValidationError):
        NearestRequest.model_validate(query)


def test_freshness_queries_ephemeral_sort_and_antimeridian_coverage(cache):
    cache.replace(
        CacheImport.model_validate(
            import_body(
                [
                    element(1, lon=-179.99, name="Synthetic Near"),
                    element(2, lon=179.9, name="Synthetic Further"),
                ],
                coverage_bounds={"south": -1.0, "north": 1.0, "west": 179.0, "east": -179.0},
            )
        )
    )
    query = query_body(max_distance_m=20_000.0, limit=1)
    query["location"]["lon"] = -180.0
    response = cache.nearest(NearestRequest.model_validate(query))
    assert response["results"][0]["key"] == "node/1"
    assert response["total_cached_matches"] == 2
    assert response["within_declared_bounds"] is True
    assert "location" not in response
    cache.clock = lambda: NOW + 8 * 86400
    assert cache.status()["cache_freshness"] == "import_stale"
    with cache.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM poi_cache_entries").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM poi_cache_meta").fetchone()[0] == 1
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE '%fix%'").fetchall()


def test_empty_offline_cache_is_not_negative_map_evidence(cache):
    response = cache.nearest(NearestRequest.model_validate(query_body()))
    assert response["kind"] == "no_cached_matches"
    assert response["coverage_complete"] is False
    assert "may be missing" in response["empty_result_meaning"]
    assert response["cache"]["network_fetch_performed"] is False


def test_only_supported_category_and_center_contract():
    for field, value in [("category", "anything"), ("limit", 21), ("max_distance_m", True)]:
        with pytest.raises(ValidationError):
            NearestRequest.model_validate(query_body(**{field: value}))
    body = import_body([element() | {"tags": {"shop": "doityourself"}}])
    assert CacheImport.model_validate(body).elements[0].coordinates.lat == 0


def test_api_cache_and_delete_all_erase_coordinates(api):
    from uuid import uuid4

    client, app = api
    response = client.put("/api/poi/cache", json=import_body())
    assert response.status_code == 200, response.text
    status = response.json()
    query = query_body()
    query["location"]["captured_at"] = datetime.now(UTC).isoformat()
    response = client.post("/api/poi/nearest", json=query)
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["key"] == "node/1"
    malformed = import_body(expected_generation=status["generation"], element_count=2)
    assert client.put("/api/poi/cache", json=malformed).status_code == 422
    assert client.get("/api/poi/cache").json()["record_count"] == 1
    response = client.request(
        "DELETE",
        "/api/data",
        json={
            "confirmed": True,
            "confirmation": "DELETE ALL LOCAL DATA",
            "idempotency_key": str(uuid4()),
            "expected_generation": status["generation"],
        },
    )
    assert response.status_code == 200, response.text
    cleared = client.get("/api/poi/cache").json()
    assert cleared["record_count"] == 0
    assert cleared["dataset_label"] is None
    assert client.put("/api/poi/cache", json=import_body()).status_code == 409
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM poi_cache_entries").fetchone()[0] == 0


def test_api_body_bound_security_and_strict_json(api):
    client, _ = api
    body = import_body()
    bad_json = json.dumps(body).replace('"confirmed": true', '"confirmed": true, "confirmed": true')
    assert (
        client.put(
            "/api/poi/cache", content=bad_json, headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    assert (
        client.put("/api/poi/cache", json=body, headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )
    assert (
        client.put(
            "/api/poi/cache",
            content=" " * (MAX_IMPORT_BYTES + 1),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    client.cookies.clear()
    assert client.get("/api/poi/cache").status_code == 401
