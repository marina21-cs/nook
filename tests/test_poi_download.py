"""Source responses are synthetic: no live Overpass acceptance is implied."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import AppError
from app.poi_download import AreaDownload, AreaDownloader, area_bounds, snapshot
from app.requests import RequestRegistry


def body(**overrides):
    return {
        "confirmed": True,
        "consent_to_share_area": True,
        "request_id": str(uuid4()),
        "expected_generation": 0,
        "label": "Synthetic public test area",
        "center": {"lat": 14.59, "lon": 120.98},
        "radius_m": 250,
        **overrides,
    }


def raw(**overrides):
    data = {
        "osm3s": {"timestamp_osm_base": "2026-10-09T00:00:00Z"},
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 14.59,
                "lon": 120.98,
                "tags": {"amenity": "cafe", "name": "Synthetic café"},
            },
            {
                "type": "way",
                "id": 1,
                "center": {"lat": 14.5901, "lon": 120.9801},
                "tags": {"shop": "convenience", "name": "Synthetic shop"},
            },
        ],
        **overrides,
    }
    return json.dumps(data).encode()


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_explicit_area_disclosure_consent(value):
    with pytest.raises(ValidationError):
        AreaDownload.model_validate(body(consent_to_share_area=value))


@pytest.mark.parametrize("radius", [0, 99, 1001, True, "250"])
def test_bounded_area(radius):
    with pytest.raises(ValidationError):
        AreaDownload.model_validate(body(radius_m=radius))


def test_response_identity_and_geometry():
    request = AreaDownload.model_validate(body())
    result = snapshot(raw(), request, area_bounds(request))
    assert [(e.type, e.id) for e in result.elements] == [("node", 1), ("way", 1)]
    assert result.element_count == 2


@pytest.mark.parametrize(
    "data", [b"{}", b"not json", raw(remark="runtime error"), raw(elements=[{}])]
)
def test_invalid_source_rejected(data):
    request = AreaDownload.model_validate(body())
    with pytest.raises(AppError):
        snapshot(data, request, area_bounds(request))


def test_oversized_source_count_never_silently_truncates():
    request = AreaDownload.model_validate(body())
    with pytest.raises(AppError) as exc:
        snapshot(raw(elements=[{}] * 251), request, area_bounds(request))
    assert exc.value.status == 413


def test_download_disabled_has_no_network(api, monkeypatch):
    client, app = api

    async def fail(_):
        raise AssertionError("Source must not run while disabled")

    monkeypatch.setattr(app.state.area_downloader, "fetch", fail)
    assert client.post("/api/poi/download", json=body()).status_code == 503


def test_synthetic_download_persists_then_nearest_and_clear_are_offline(api, monkeypatch):
    client, app = api
    app.state.area_downloader.enabled = True
    calls = []

    async def fake(query):
        calls.append(query)
        return raw()

    monkeypatch.setattr(app.state.area_downloader, "fetch", fake)
    response = client.post("/api/poi/download", json=body())
    assert response.status_code == 200, response.text
    cache = response.json()["cache"]
    assert cache["source"] == "osm_overpass_download" and cache["fetched_at"]
    assert cache["download_provenance"]["download_bytes"] == len(raw())
    assert cache["coverage_complete"] is False and cache["source_freshness"] == "unknown"
    assert client.get("/api/status").json()["item_count"] == 0
    query = {
        "confirmed": True,
        "location": {
            "lat": 14.59,
            "lon": 120.98,
            "captured_at": datetime.now(UTC).isoformat(),
            "accuracy_m": 1000.0,
        },
        "category": "cafe",
    }
    result = client.post("/api/poi/nearest", json=query)
    assert result.status_code == 200
    assert result.json()["results"][0]["name"] == "Synthetic café" and len(calls) == 1
    # New cache wrapper / database connection sees persisted provenance.
    from app.poi import POICache

    assert (
        POICache(app.state.repo.db).status()["download_provenance"] == cache["download_provenance"]
    )
    deleted = client.request(
        "DELETE",
        "/api/poi/cache",
        json={"confirmed": True, "expected_generation": cache["generation"]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["download_provenance"] is None and len(calls) == 1


def test_stale_generation_download_does_not_replace(api, monkeypatch):
    client, app = api
    app.state.area_downloader.enabled = True

    async def fake(_):
        return raw()

    monkeypatch.setattr(app.state.area_downloader, "fetch", fake)
    response = client.post("/api/poi/download", json=body(expected_generation=99))
    assert response.status_code == 409 and app.state.poi.status()["record_count"] == 0


def test_precancelled_download_does_not_fetch(api, monkeypatch):
    client, app = api
    app.state.area_downloader.enabled = True
    data = body()
    client.post("/api/requests/" + data["request_id"] + "/cancel")

    async def fail(_):
        raise AssertionError("Cancelled before source retrieval")

    monkeypatch.setattr(app.state.area_downloader, "fetch", fail)
    assert client.post("/api/poi/download", json=data).status_code == 409


def test_running_cancel_never_commits():
    async def exercise():
        registry = RequestRegistry()
        started = asyncio.Event()
        worker = AreaDownloader(True)

        async def fake(_):
            started.set()
            await asyncio.sleep(60)
            return raw()

        worker.fetch = fake

        class Cache:
            def replace(self, *args, **kwargs):
                raise AssertionError("Cancelled download must not commit")

        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(requests=registry, poi=Cache()))
        )
        data = AreaDownload.model_validate(body())
        task = asyncio.create_task(worker.run(data, request))
        await started.wait()
        registry.cancel(str(data.request_id))
        with pytest.raises(AppError) as exc:
            await task
        assert exc.value.code == "request_cancelled" and worker.active is False

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "status,headers,chunks,code",
    [
        (429, {}, [], "area_source_busy"),
        (302, {"location": "https://other.invalid"}, [], "area_source_failed"),
        (200, {"content-encoding": "gzip"}, [], "area_source_failed"),
        (200, {"content-length": str(1024 * 1024 + 1)}, [], "area_download_limit"),
        (200, {}, [b"x" * 16384] * 65, "area_download_limit"),
    ],
)
def test_synthetic_transport_limits(monkeypatch, status, headers, chunks, code):
    """Synthetic transport, not evidence of live network behavior."""
    from contextlib import asynccontextmanager

    import httpx

    class Response:
        status_code = status

        async def aiter_raw(self, chunk_size):
            for chunk in chunks:
                yield chunk

    response = Response()
    response.headers = headers

    class Client:
        def __init__(self, **options):
            assert options["follow_redirects"] is False
            assert options["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def stream(self, method, url, **kwargs):
            from app.poi_download import ENDPOINT

            assert method == "POST" and url == ENDPOINT
            yield response

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    with pytest.raises(AppError) as error:
        asyncio.run(AreaDownloader(True).fetch("synthetic test query"))
    assert error.value.code == code


def test_synthetic_network_error_preserves_previous_cache(api, monkeypatch):
    import httpx

    client, app = api
    app.state.area_downloader.enabled = True

    async def initial(_):
        return raw()

    monkeypatch.setattr(app.state.area_downloader, "fetch", initial)
    assert client.post("/api/poi/download", json=body()).status_code == 200
    before = client.get("/api/poi/cache").json()
    app.state.area_downloader.last_attempt = float("-inf")

    async def unavailable(_):
        raise httpx.ConnectError("synthetic network unavailable")

    monkeypatch.setattr(app.state.area_downloader, "fetch", unavailable)
    response = client.post("/api/poi/download", json=body(expected_generation=before["generation"]))
    assert response.status_code == 503
    after = client.get("/api/poi/cache").json()
    assert before["download_provenance"] == after["download_provenance"]
    assert before["generation"] == after["generation"]
