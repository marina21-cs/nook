import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import AppError
from app.evidence_store import EvidenceStore
from app.main import create_app
from tests.conftest import BASE, captured, commit_payload, mutation, recall, upload


def test_restart_persists_items_photos_and_cleans_drafts_orphans(tmp_path):
    settings = Settings(data_dir=tmp_path / "data")
    first = create_app(settings)
    with TestClient(first, base_url=BASE) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        item = captured(client)[0]
        draft = upload(client)
        orphan = str(uuid4())
        first.state.store.finalize(draft["id"], orphan)  # Crash window before metadata commit.
        old_cookie = client.cookies.get("app_session")
    second = create_app(settings)
    with TestClient(second, base_url=BASE) as client:
        client.cookies.set("app_session", old_cookie)
        assert client.get("/api/items").status_code == 401
        client.cookies.clear()
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        assert client.get(f"/api/items/{item['id']}").json() == item
        assert recall(client)["items"][0]["id"] == item["id"]
        assert client.get(item["current_observation"]["photo"]["url"]).status_code == 200
        assert not list(second.state.store.drafts.iterdir())
        assert not second.state.store.path(orphan).exists()
        assert client.get(draft["photo_url"]).status_code == 404


def test_failure_after_file_finalization_rolls_back_and_retry_succeeds(api, monkeypatch):
    client, app = api
    draft = upload(client)
    body = commit_payload()
    original = app.state.repo.observation

    def disk_full(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic disk full")

    monkeypatch.setattr(app.state.repo, "observation", disk_full)
    failed = client.post(f"/api/captures/{draft['id']}/commit", json=body)
    assert failed.status_code == 503
    assert client.get("/api/items").json()["total"] == 0
    assert client.get(draft["photo_url"]).status_code == 200
    assert not list(app.state.store.photos.iterdir())
    monkeypatch.setattr(app.state.repo, "observation", original)
    assert client.post(f"/api/captures/{draft['id']}/commit", json=body).status_code == 200
    assert client.get("/api/items").json()["total"] == 1


def test_file_write_failure_never_reports_saved(api, monkeypatch):
    client, app = api
    draft = upload(client)

    def fail(*args, **kwargs):
        raise OSError("synthetic disk full")

    monkeypatch.setattr(app.state.store, "finalize", fail)
    response = client.post(f"/api/captures/{draft['id']}/commit", json=commit_payload())
    assert response.status_code == 503
    assert client.get("/api/items").json()["total"] == 0
    assert client.get(draft["photo_url"]).status_code == 200


def test_private_permissions_and_storage_ownership(api, tmp_path):
    client, app = api
    captured(client)
    assert app.state.store.root.stat().st_mode & 0o777 == 0o700
    assert app.state.repo.db.path.stat().st_mode & 0o777 == 0o600
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in app.state.store.photos.iterdir())
    unrelated = tmp_path / "foreign"
    unrelated.mkdir()
    (unrelated / "notes.txt").write_text("preserve")
    with pytest.raises(AppError) as error:
        EvidenceStore(Settings(data_dir=unrelated))
    assert error.value.code == "unowned_storage"
    assert (unrelated / "notes.txt").read_text() == "preserve"
    with pytest.raises(AppError) as error:
        EvidenceStore(app.state.settings)
    assert error.value.code == "storage_busy"


def test_symlink_evidence_cannot_read_arbitrary_file(api, tmp_path):
    client, app = api
    item = captured(client)[0]
    photo = item["current_observation"]["photo"]
    original = app.state.store.path(photo["id"])
    original.unlink()
    secret = tmp_path / "synthetic-secret.txt"
    secret.write_text("should not read")
    original.symlink_to(secret)
    assert client.get(photo["url"]).status_code == 404
    assert not client.get(f"/api/items/{item['id']}").json()["current_observation"]["photo"][
        "available"
    ]
    client.request(
        "DELETE", f"/api/items/{item['id']}", json=mutation(item, evidence_scope="unreferenced")
    )
    assert secret.read_text() == "should not read"
