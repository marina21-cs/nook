import asyncio
from dataclasses import replace

import pytest

from app.errors import AppError
from tests.conftest import captured, commit_payload, upload


def test_draft_item_and_evidence_quotas_preserve_existing_data(api):
    client, app = api
    item = captured(client)[0]
    app.state.repo.settings = replace(app.state.repo.settings, max_items=1, max_drafts=1)
    first = upload(client)
    blocked = client.post("/api/captures", content=b"png", headers={"Content-Type": "image/png"})
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "draft_limit"
    blocked = client.post(f"/api/captures/{first['id']}/commit", json=commit_payload())
    assert blocked.status_code == 409
    assert client.get(f"/api/items/{item['id']}").json() == item
    client.delete(f"/api/captures/{first['id']}")
    app.state.store.settings = replace(app.state.store.settings, max_evidence_bytes=1)
    from tests.conftest import image_bytes

    blocked = client.post(
        "/api/captures", content=image_bytes(), headers={"Content-Type": "image/png"}
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "evidence_quota"
    assert client.get(f"/api/items/{item['id']}").json() == item


def test_migration_is_idempotent_and_future_version_is_rejected(api):
    _, app = api
    database = app.state.repo.db
    database.migrate()
    with database.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(AppError) as error:
        database.migrate()
    assert error.value.code == "newer_database"
    with database.connect() as conn:
        conn.execute("PRAGMA user_version=3")


def test_chunked_upload_limits_apply_without_content_length(api):
    # Invoke ASGI boundary directly to prove checks are independent of Content-Length.
    client, app = api
    cookie = client.cookies.get("app_session")
    chunks = [b"x" * (6 * 1024 * 1024), b"y" * (5 * 1024 * 1024)]
    response = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/captures",
        "raw_path": b"/api/captures",
        "query_string": b"",
        "root_path": "",
        "server": ("127.0.0.1", 8765),
        "client": ("127.0.0.1", 1234),
        "headers": [
            (b"host", b"127.0.0.1:8765"),
            (b"cookie", ("app_session=" + cookie).encode()),
            (b"x-csrf-token", client.headers["x-csrf-token"].encode()),
            (b"content-type", b"image/png"),
        ],
    }

    async def receive():
        if chunks:
            return {"type": "http.request", "body": chunks.pop(0), "more_body": bool(chunks)}
        return {"type": "http.disconnect"}

    async def send(message):
        response.append(message)

    asyncio.run(app(scope, receive, send))
    assert response[0]["status"] == 413
    assert client.get("/api/items").json()["total"] == 0
