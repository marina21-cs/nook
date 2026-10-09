import io
import socket
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app

BASE = "http://127.0.0.1:8765"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any actual outbound connection. In-process ASGI tests still work."""

    def deny(*args, **kwargs):
        raise OSError("Network blocked by the test; no firewall changes")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)

    async def fail_send(self, request, *args, **kwargs):
        raise httpx.ConnectError(
            "Local runtime intentionally absent in behavior tests", request=request
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", fail_send)


@pytest.fixture
def api(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / "data"))
    with TestClient(app, base_url=BASE) as client:
        csrf = client.get("/api/session").json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        yield client, app


def image_bytes(fmt="PNG", size=(128, 96), color="blue", exif=None):
    out = io.BytesIO()
    image = Image.new("RGB", size, color)
    image.save(out, fmt, **({"exif": exif} if exif else {}))
    return out.getvalue()


def upload(client, source="camera", **kwargs):
    response = client.post(
        "/api/captures?source=" + source,
        content=image_bytes(**kwargs),
        headers={
            "Content-Type": "image/png" if kwargs.get("fmt", "PNG") == "PNG" else "image/jpeg"
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def commit_payload(names=("blue craft scissors",), **overrides):
    return {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "location": "Hall cabinet → top drawer",
        "make_current": True,
        "rows": [{"identity": "new", "personal_name": name} for name in names],
        **overrides,
    }


def captured(client, names=("blue craft scissors",), **overrides):
    draft = upload(client)
    payload = commit_payload(names, **overrides)
    response = client.post(f"/api/captures/{draft['id']}/commit", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def manual(client, name="blue craft scissors", location="Hall drawer", **overrides):
    payload = {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "personal_name": name,
        "location": location,
        **overrides,
    }
    response = client.post("/api/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["items"][0]


def recall(client, query="Where did I put my blue craft scissors?", **overrides):
    response = client.post(
        "/api/recall", json={"query": query, "request_id": str(uuid4()), **overrides}
    )
    assert response.status_code == 200, response.text
    return response.json()


def mutation(item, **overrides):
    return {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "expected_revision": item["revision"],
        **overrides,
    }
