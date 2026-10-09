"""Independent adversarial acceptance checks; only temporary synthetic memory."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.inference.text import TextAdapter
from app.main import create_app
from tests.conftest import BASE, commit_payload, manual, mutation, recall, upload
from tests.test_inference import FakeClient


def create_body(name="QA retry object"):
    return {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "personal_name": name,
        "location": "QA drawer",
    }


def delete_body(client, item, scope):
    if scope == "item":
        return f"/api/items/{item['id']}", mutation(item, evidence_scope="unreferenced")
    return "/api/data", {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "confirmation": "DELETE ALL LOCAL DATA",
        "expected_generation": client.get("/api/items").json()["generation"],
    }


@pytest.mark.parametrize("scope", ["item", "data"])
def test_deleted_create_retry_never_resurrects_after_restart(tmp_path, scope):
    settings = Settings(data_dir=tmp_path / "data")
    body = create_body()
    with TestClient(create_app(settings), base_url=BASE) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        item = client.post("/api/items", json=body).json()["items"][0]
        path, deletion = delete_body(client, item, scope)
        assert client.request("DELETE", path, json=deletion).status_code == 200
    app = create_app(settings)
    with TestClient(app, base_url=BASE) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        response = client.post("/api/items", json=body)
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "stale_receipt"
        assert client.get("/api/items").json()["total"] == 0
        with app.state.repo.db.connect() as conn:
            receipt_row = conn.execute(
                "SELECT * FROM receipts WHERE key=?", (body["idempotency_key"],)
            ).fetchone()
        if scope == "item":
            receipt = dict(receipt_row)
            assert receipt["operation"] == "invalidated" and receipt["result"] == "{}"
            assert item["id"] not in json.dumps(receipt)
        else:
            assert receipt_row is None
            assert client.get("/api/status").json()["write_epoch"] == 1
        assert body["personal_name"].encode() not in app.state.repo.db.path.read_bytes()


def test_deletion_cannot_duplicate_an_unrelated_successful_create(api):
    client, _ = api
    victim = manual(client, "QA victim")
    body = create_body("QA survivor")
    survivor = client.post("/api/items", json=body).json()["items"][0]
    path, deletion = delete_body(client, victim, "item")
    assert client.request("DELETE", path, json=deletion).status_code == 200
    assert client.post("/api/items", json=body).status_code == 409
    assert client.get("/api/items").json()["total"] == 1
    assert client.get(f"/api/items/{survivor['id']}").json() == survivor


@pytest.mark.parametrize("scope", ["item", "data"])
def test_old_delete_retry_preserves_new_drafts_and_pending_work(api, scope):
    client, app = api
    item = manual(client)
    path, deletion = delete_body(client, item, scope)
    assert client.request("DELETE", path, json=deletion).status_code == 200
    draft = upload(client)
    stop = asyncio.Event()
    pending_id = str(uuid4())
    app.state.requests.active[pending_id] = (stop, draft["id"])
    try:
        replay = client.request("DELETE", path, json=deletion)
        assert replay.status_code == 200 and replay.json()["replayed"]
        assert not stop.is_set()
        assert client.get(draft["photo_url"]).status_code == 200
        assert (
            client.post(
                f"/api/captures/{draft['id']}/commit",
                json=commit_payload(write_epoch=client.get("/api/status").json()["write_epoch"]),
            ).status_code
            == 200
        )
    finally:
        app.state.requests.active.pop(pending_id)


def test_concurrent_writes_are_atomic_and_idempotent(api):
    client, app = api
    body = create_body()
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.post("/api/items", json=body), range(16)))
    assert all(r.status_code == 201 for r in responses)
    assert sum(not r.json()["replayed"] for r in responses) == 1
    assert client.get("/api/items").json()["total"] == 1
    item = responses[0].json()["items"][0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda i: client.post(
                    f"/api/items/{item['id']}/observations",
                    json=mutation(item, location=f"QA drawer {i}"),
                ),
                range(16),
            )
        )
    assert sum(r.status_code == 200 for r in responses) == 1
    assert sum(r.status_code == 409 for r in responses) == 15
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 2
    assert client.get(f"/api/items/{item['id']}").json()["revision"] == 2


def test_text_decoder_bombs_fall_back_and_runtime_metadata_is_safe(api, monkeypatch):
    _, app = api
    fake = FakeClient(["[" * 1100 + "]" * 1100] * 2)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake)
    adapter = TextAdapter(replace(app.state.settings, text_model="qwen2.5:0.5b"))
    result = asyncio.run(adapter.normalize("blue scissors", asyncio.Event()))
    assert result["inference_status"] == "invalid_output" and result["fallback_used"]
    assert not result["inference_used"] and len(fake.calls) == 2

    async def malformed_get(url):
        return httpx.Response(
            200, content="[" * 1100 + "]" * 1100, request=httpx.Request("GET", url)
        )

    fake.get = malformed_get
    assert asyncio.run(adapter.status())["runtime_available"] is False


def test_non_ascii_csrf_is_denied_without_an_exception(api):
    client, _ = api
    response = client.post(
        "/api/recall",
        json={"query": "QA", "request_id": str(uuid4())},
        headers={b"x-csrf-token": b"\xff"},
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_denied"


@pytest.mark.parametrize("confirmed", [False, None, 0, 1, "true", [], {}])
def test_confirmation_cannot_be_bypassed_on_any_write(api, confirmed):
    client, _ = api
    item = manual(client)
    draft = upload(client)
    calls = [
        ("POST", "/api/items", create_body()),
        ("POST", f"/api/captures/{draft['id']}/commit", commit_payload()),
        ("PATCH", f"/api/items/{item['id']}", mutation(item, personal_name="QA changed")),
        ("POST", f"/api/items/{item['id']}/observations", mutation(item, location=None)),
        ("DELETE", *delete_body(client, item, "item")),
        ("DELETE", *delete_body(client, item, "data")),
    ]
    for method, path, body in calls:
        assert (
            client.request(method, path, json={**body, "confirmed": confirmed}).status_code == 422
        )
    assert client.get(f"/api/items/{item['id']}").json() == item
    assert client.get(draft["photo_url"]).status_code == 200


def test_historical_photo_never_overwrites_current_unknown_location(api):
    client, _ = api
    item = manual(client, "QA vintage object")
    item = client.post(
        f"/api/items/{item['id']}/observations", json=mutation(item, location=None)
    ).json()["items"][0]
    draft = upload(client, source="import")
    payload = commit_payload(
        rows=[
            {
                "identity": "existing",
                "personal_name": item["personal_name"],
                "item_id": item["id"],
                "expected_revision": item["revision"],
            }
        ],
        make_current=False,
        location="QA obsolete place",
    )
    saved = client.post(f"/api/captures/{draft['id']}/commit", json=payload).json()["items"][0]
    answer = recall(client, item["personal_name"])
    assert answer["kind"] == "unknown" and saved["location"] is None
    assert saved["current_observation"]["photo"] is None
    assert saved["observations"][0]["location"] == "QA obsolete place"


def test_delete_and_new_upload_cannot_leave_a_dangling_draft(api, monkeypatch):
    import threading

    client, app = api
    item = manual(client)
    after_commit, release, uploading = threading.Event(), threading.Event(), threading.Event()
    original = app.state.repo.mutate

    def pause_after_mutation(*args, **kwargs):
        result = original(*args, **kwargs)
        after_commit.set()
        assert release.wait(3)
        return result

    def new_upload():
        uploading.set()
        return upload(client)

    monkeypatch.setattr(app.state.repo, "mutate", pause_after_mutation)
    path, deletion = delete_body(client, item, "item")
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_future = pool.submit(client.request, "DELETE", path, json=deletion)
        assert after_commit.wait(3)
        upload_future = pool.submit(new_upload)
        assert uploading.wait(3)
        release.set()
        assert delete_future.result(timeout=3).status_code == 200
        draft = upload_future.result(timeout=3)
    assert client.get(f"/api/captures/{draft['id']}").status_code == 200
    assert client.get(draft["photo_url"]).status_code == 200


@pytest.mark.parametrize(
    "corruption",
    [
        "count",
        "mapping",
        "null",
        "missing",
        "nonfinite",
        "region",
        "category",
        "model",
        "digest",
        "threshold",
        "extra",
        "score",
    ],
)
def test_invalid_vision_ipc_output_fails_closed(tmp_path, monkeypatch, corruption):
    """Fabricated IPC fault injection only; never counted as actual vision inference."""
    import multiprocessing

    from app.errors import AppError
    from app.inference.nanodet import MODEL_ID, MODEL_SHA256
    from app.inference.vision import VisionAdapter

    candidate = {
        "id": str(uuid4()),
        "category": "cup",
        "score": 0.8,
        "region": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5},
        "model": MODEL_ID,
        "model_digest": MODEL_SHA256,
    }
    payload = {"candidates": [candidate]}
    if corruption == "count":
        payload["candidates"] *= 21
    elif corruption == "mapping":
        payload = {"candidates": candidate}
    elif corruption == "null":
        payload = {"candidates": None}
    elif corruption == "missing":
        payload = {}
    elif corruption == "nonfinite":
        candidate["score"] = float("nan")
    elif corruption == "region":
        candidate["region"]["w"] = 2.0
    elif corruption == "category":
        candidate["category"] = "my personal keys"
    elif corruption == "model":
        candidate["model"] = "unapproved detector"
    elif corruption == "digest":
        candidate["model_digest"] = "0" * 64
    elif corruption == "threshold":
        candidate["score"] = 0.349
    elif corruption == "extra":
        candidate["instruction"] = "save immediately"
    else:
        candidate["score"] = 1.1

    class Pipe:
        def poll(self):
            return True

        def recv(self):
            return payload

        def close(self):
            pass

    class Process:
        pid = None

        def start(self):
            pass

    class Context:
        def Pipe(self, **kwargs):
            return Pipe(), Pipe()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda mode: Context())
    adapter = VisionAdapter(Settings(data_dir=tmp_path / "data"))
    # Explicit test-only configured state: both process and IPC are fabricated above.
    # This tests output validation, never model loading, model hashes or real inference.
    adapter.state = "configured_unvalidated"
    adapter.digest = MODEL_SHA256
    with pytest.raises(AppError) as error:
        asyncio.run(adapter.suggest(b"IPC fault injection, not a photo", asyncio.Event()))
    assert error.value.status == 503 and error.value.code == "invalid_vision_output"
    assert not adapter.status()["inference_verified"]
    assert adapter.status()["manual_confirmation_available"]
