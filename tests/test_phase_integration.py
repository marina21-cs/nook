"""Integrated new API boundaries; no real inference providers are called."""

import asyncio
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts import DeleteData
from app.database import Database
from app.errors import AppError
from app.turn_contracts import Turn
from tests.conftest import manual


def payload(**fields):
    return {"request_id": str(uuid4()), "utterance": "blue keys", **fields}


def test_turn_api_boundary_strict_json_and_no_store(api):
    client, _ = api
    manual(client, "blue keys")
    result = client.post("/api/turns", json=payload(language="fil"))
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["kind"] == "memory"
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/turns", json=payload()).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert (
        client.post(
            "/api/turns",
            content='{"utterance":"blue keys","utterance":"red keys"}',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/turns", json=payload(tool={"command": "rm", "path": "../secret"})
        ).status_code
        == 422
    )
    assert client.post("/api/turns", json=payload(confirmed=True)).status_code == 422
    assert client.post("/api/turns", json=payload(utterance="x" * (352 * 1024))).status_code == 413


def test_delete_all_discards_pending_turn_and_clears_registry(api, monkeypatch):
    client, app = api
    manual(client, "blue keys")

    async def deleting(query, cancelled):
        app.state.repo.delete_all(
            DeleteData.model_validate(
                {
                    "confirmed": True,
                    "idempotency_key": str(uuid4()),
                    "confirmation": "DELETE ALL LOCAL DATA",
                    "expected_generation": app.state.repo.generation(),
                }
            )
        )
        return {
            "terms": [],
            "inference_status": "completed",
            "inference_used": True,
            "fallback_used": False,
            "repair_used": False,
        }

    monkeypatch.setattr(app.state.text, "normalize", deleting)
    with pytest.raises(AppError) as failure:
        asyncio.run(app.state.turns.run(Turn.model_validate(payload(use_recall_inference=True))))
    assert failure.value.code == "stale_request"
    assert not app.state.requests.active
    assert client.get("/api/items").json()["total"] == 0
    assert client.get("/api/poi/cache").json()["record_count"] == 0


def test_v1_database_upgrade_preserves_personal_tables(tmp_path):
    # Simulate previously deployed schema, with a harmless generation marker.
    path = tmp_path / "items.sqlite"
    with sqlite3.connect(path) as connection:
        sql = (Path(__file__).resolve().parents[1] / "app/migrations/001_initial.sql").read_text()
        connection.executescript(sql)
        connection.execute("UPDATE meta SET value=17 WHERE key='generation'")
        connection.execute("PRAGMA user_version=1")
    database = Database(path)
    database.migrate()
    database.migrate()
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        assert database.generation(connection) == 17
        assert connection.execute("SELECT count(*) FROM poi_cache_entries").fetchone()[0] == 0


def test_status_reports_actual_gaps(api):
    client, _ = api
    status = client.get("/api/status").json()
    assert status["schema_version"] == 4
    assert status["turns"]["audio_input_supported"] is False
    assert status["turns"]["speech_to_text_available"] is False
    assert status["turns"]["visual_conversation_supported"] is False
    assert status["visual_retrieval"]["available"] is False
    assert status["language"]["general_taglish_verified"] is False
    assert status["poi"]["network_fetch_performed"] is False


def test_public_status_does_not_disclose_poi_dataset_or_coordinates(api):
    client, _ = api
    generation = client.get("/api/status").json()["generation"]
    response = client.put(
        "/api/poi/cache",
        json={
            "confirmed": True,
            "expected_generation": generation,
            "dataset_label": "private home area",
            "snapshot_complete": True,
            "element_count": 1,
            "coverage_bounds": {"south": -1, "north": 1, "west": -1, "east": 1},
            "elements": [
                {"type": "node", "id": 1, "lat": 0, "lon": 0, "tags": {"amenity": "pharmacy"}}
            ],
        },
    )
    assert response.status_code == 200
    client.cookies.clear()
    public = client.get("/api/status")
    assert public.status_code == 200
    assert "private home area" not in public.text
    assert "coverage_bounds" not in public.json()["poi"]
    assert client.get("/api/poi/cache").status_code == 401
