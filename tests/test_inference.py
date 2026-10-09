import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from app.contracts import Candidate
from app.inference.text import TextAdapter
from app.inference.vision import VisionAdapter
from tests.conftest import manual, mutation, recall


class FakeClient:
    """Explicit test double for output validation; never counted as real inference."""

    def __init__(self, outputs, delay=0):
        self.outputs = iter(outputs)
        self.calls = []
        self.delay = delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json):
        self.calls.append((url, json))
        await asyncio.sleep(self.delay)
        content = next(self.outputs)
        if isinstance(content, Exception):
            raise content
        return httpx.Response(
            200,
            json={"done": True, "message": {"content": content}},
            request=httpx.Request("POST", url),
        )


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        '{"intent":"recall"}',
        '{"intent":"delete","terms":["blue scissors"]}',
        '{"intent":"recall","terms":["scissors"]}',  # Missing distinguishing word.
        '{"intent":"recall","terms":["blue scissors"],"location":"invented"}',
        '{"intent":"recall","intent":"recall","terms":["blue scissors"]}',
        "run bash -c rm",
        '{"intent":"recall","terms":[42]}',
    ],
)
def test_invalid_model_output_repaired_once_then_falls_back(api, monkeypatch, content):
    _, app = api
    fake = FakeClient([content, content])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake)
    adapter = TextAdapter(replace(app.state.settings, text_model="qwen2.5:0.5b"))
    outcome = asyncio.run(adapter.normalize("where are my blue scissors", asyncio.Event()))
    assert not outcome["inference_used"] and outcome["fallback_used"]
    assert outcome["inference_status"] == "invalid_output" and outcome["repair_used"]
    assert len(fake.calls) == 2
    assert all(url == "http://127.0.0.1:11434/api/chat" for url, _ in fake.calls)
    assert all("tools" not in payload for _, payload in fake.calls)


def test_valid_repair_is_explicit_and_has_schema(api, monkeypatch):
    _, app = api
    fake = FakeClient(["{}", '{"intent":"recall","terms":["blue scissors"]}'])
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake)
    adapter = TextAdapter(replace(app.state.settings, text_model="qwen2.5:0.5b"))
    result = asyncio.run(adapter.normalize("blue scissors", asyncio.Event()))
    assert result["inference_used"] and result["repair_used"] and not result["fallback_used"]
    payload = fake.calls[0][1]
    assert payload["format"]["additionalProperties"] is False
    assert payload["options"]["temperature"] == 0


def test_text_timeout_and_unavailable_are_fallbacks(api, monkeypatch):
    _, app = api
    adapter = TextAdapter(
        replace(app.state.settings, text_model="qwen2.5:0.5b", model_timeout=0.01)
    )
    fake = FakeClient(["{}"], delay=1)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: fake)
    assert (
        asyncio.run(adapter.normalize("blue scissors", asyncio.Event()))["inference_status"]
        == "timeout"
    )
    fake = FakeClient([httpx.ConnectError("runtime missing")])
    assert (
        asyncio.run(adapter.normalize("blue scissors", asyncio.Event()))["inference_status"]
        == "unavailable"
    )


def test_model_configuration_and_candidate_validation(api, tmp_path):
    _, app = api
    with pytest.raises(ValueError):
        replace(app.state.settings, text_model="remote-model")
    model = tmp_path / "not-a-model.tflite"
    model.write_bytes(b"synthetic invalid model; not weights")
    adapter = VisionAdapter(replace(app.state.settings, vision_model=model, vision_sha256="0" * 64))
    assert adapter.status()["state"] == "checksum_mismatch"
    assert not adapter.status()["inference_verified"]
    for invalid in [
        {"category": "bottle", "action": "execute"},
        {
            "id": str(uuid4()),
            "category": "bottle",
            "score": 2,
            "region": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            "model": "test",
            "model_digest": "test",
        },
    ]:
        with pytest.raises(ValueError):
            Candidate.model_validate_json(json.dumps(invalid))


def test_cancel_pending_recall_discards_result(api, monkeypatch):
    client, app = api
    manual(client)
    started = threading.Event()

    async def pending(query, cancelled):
        started.set()
        await cancelled.wait()
        return {
            "terms": [],
            "inference_status": "cancelled",
            "inference_used": False,
            "fallback_used": True,
            "repair_used": False,
        }

    monkeypatch.setattr(app.state.text, "normalize", pending)
    request_id = str(uuid4())
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post,
            "/api/recall",
            json={"query": "blue craft scissors", "request_id": request_id, "use_inference": True},
        )
        assert started.wait(3)
        assert client.post(f"/api/requests/{request_id}/cancel").status_code == 200
        result = future.result(timeout=3)
    assert result.status_code == 409 and result.json()["error"]["code"] == "request_cancelled"


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_pending_recall_never_returns_old_or_deleted_records(api, monkeypatch, action):
    client, app = api
    item = manual(client)
    started, release = threading.Event(), threading.Event()

    async def pending(query, cancelled):
        started.set()
        while not release.is_set() and not cancelled.is_set():
            await asyncio.sleep(0.01)
        return {
            "terms": [],
            "inference_status": "disabled",
            "inference_used": False,
            "fallback_used": True,
            "repair_used": False,
        }

    monkeypatch.setattr(app.state.text, "normalize", pending)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post,
            "/api/recall",
            json={
                "query": "blue craft scissors",
                "request_id": str(uuid4()),
                "use_inference": True,
            },
        )
        assert started.wait(3)
        if action == "edit":
            assert (
                client.patch(
                    f"/api/items/{item['id']}", json=mutation(item, personal_name="new name")
                ).status_code
                == 200
            )
        else:
            assert (
                client.request(
                    "DELETE",
                    f"/api/items/{item['id']}",
                    json=mutation(item, evidence_scope="unreferenced"),
                ).status_code
                == 200
            )
        release.set()
        response = future.result(timeout=3)
    assert response.status_code == 409 and "items" not in response.json()


def test_offline_unseen_upload_query_and_status(api):
    # Autouse fixture blocks actual outbound sockets; this is backend behavior, not real AI proof.
    client, _ = api
    from tests.conftest import captured

    item = captured(client, names=("novel purple tool",))[0]
    result = recall(client, "Where did I put the novel purple tool?")
    assert result["items"][0]["id"] == item["id"]
    status = client.get("/api/status").json()
    assert not status["cloud_dependency"] and not status["vision"]["inference_verified"]
    assert not status["text"]["runtime_available"]
    assert not status["queries_persisted"]


@pytest.mark.parametrize("action", ["discard", "edit"])
def test_pending_photo_suggestion_is_discarded_on_cancel_or_collection_change(
    api, monkeypatch, action
):
    from tests.conftest import upload

    client, app = api
    draft = upload(client)
    item = manual(client)
    started, release = threading.Event(), threading.Event()

    async def pending(encoded, cancelled):
        # Explicit race test double, not real detector inference.
        started.set()
        while not release.is_set() and not cancelled.is_set():
            await asyncio.sleep(0.01)
        return [], 1.0

    monkeypatch.setattr(app.state.vision, "suggest", pending)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.post, f"/api/captures/{draft['id']}/suggest", json={"request_id": str(uuid4())}
        )
        assert started.wait(3)
        if action == "discard":
            assert client.delete(f"/api/captures/{draft['id']}").status_code == 200
        else:
            assert (
                client.patch(
                    f"/api/items/{item['id']}", json=mutation(item, personal_name="updated tool")
                ).status_code
                == 200
            )
        release.set()
        result = future.result(timeout=3)
    assert result.status_code == 409
    assert client.get("/api/items").json()["total"] == 1
    if action == "discard":
        assert client.get(draft["photo_url"]).status_code == 404
    else:
        assert client.get(f"/api/captures/{draft['id']}").json()["candidates"] == []
