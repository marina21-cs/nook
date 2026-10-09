"""Independent-review regressions: synthetic inputs, no real model inference."""

import hashlib
import io
from uuid import uuid4

import pytest
from PIL import Image

from tests.conftest import commit_payload, manual, mutation, recall, upload


def test_receipt_capacity_never_blocks_privacy_deletion(api):
    """Accelerated setup fills receipts directly; deletion itself uses the real API."""
    client, app = api
    item = manual(client)
    with app.state.repo.db.connect(write=True) as conn:
        conn.executemany(
            "INSERT INTO receipts VALUES (?,?,?,?)",
            [(str(uuid4()), "invalidated", "0" * 64, "{}") for _ in range(9999)],
        )
    deleted = client.request(
        "DELETE", f"/api/items/{item['id']}", json=mutation(item, evidence_scope="all_affected")
    )
    assert deleted.status_code == 200, deleted.text
    generation = client.get("/api/status").json()["generation"]
    reset = client.request(
        "DELETE",
        "/api/data",
        json={
            "confirmed": True,
            "idempotency_key": str(uuid4()),
            "confirmation": "DELETE ALL LOCAL DATA",
            "expected_generation": generation,
        },
    )
    assert reset.status_code == 200, reset.text
    epoch = client.get("/api/status").json()["write_epoch"]
    manual(client, write_epoch=epoch)
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM receipts").fetchone()[0] <= 10000


def test_existing_photo_preserves_omitted_metadata_and_explicit_clears(api):
    client, _ = api
    item = manual(
        client,
        name="house keys",
        aliases=["spare keys"],
        distinguishing_note="red tag",
        category="keys",
    )
    draft = upload(client)
    payload = commit_payload(
        rows=[
            {
                "identity": "existing",
                "item_id": item["id"],
                "expected_revision": item["revision"],
                "personal_name": "house keys",
            }
        ]
    )
    response = client.post(f"/api/captures/{draft['id']}/commit", json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()["items"][0]
    assert (updated["aliases"], updated["distinguishing_note"], updated["category"]) == (
        ["spare keys"],
        "red tag",
        "keys",
    )
    assert recall(client, "spare keys")["kind"] == "found"
    # Same key, changed field presence is a different write even if defaults are identical.
    payload["rows"][0].update(aliases=[], distinguishing_note="", category=None)
    conflict = client.post(f"/api/captures/{draft['id']}/commit", json=payload)
    assert conflict.status_code == 409
    draft = upload(client)
    payload["idempotency_key"] = str(uuid4())
    payload["rows"][0]["expected_revision"] = updated["revision"]
    cleared = client.post(f"/api/captures/{draft['id']}/commit", json=payload)
    assert cleared.status_code == 200, cleared.text
    value = cleared.json()["items"][0]
    assert (value["aliases"], value["distinguishing_note"], value["category"]) == ([], "", None)
    assert recall(client, "spare keys")["kind"] == "unknown"


@pytest.mark.parametrize(
    "name",
    ["do not disturb sign", "delete key", "huwag pumasok sign", "ignore instructions poster"],
)
def test_confirmed_literal_labels_can_contain_guard_words(api, name):
    client, _ = api
    manual(client, name=name)
    assert recall(client, name)["kind"] == "found"
    assert recall(client, "where is my " + name + "?")["kind"] == "found"
    assert recall(client, "not " + name)["kind"] == "unknown"
    assert recall(client, "delete " + name)["kind"] == "unknown"
    assert client.get("/api/items").json()["total"] == 1


def test_mpo_deliberately_rejected_without_persisting(api):
    client, _ = api
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(
        output, format="MPO", save_all=True, append_images=[Image.new("RGB", (16, 16), "blue")]
    )
    response = client.post(
        "/api/captures", content=output.getvalue(), headers={"Content-Type": "image/jpeg"}
    )
    assert response.status_code == 415
    assert client.get("/api/items").json()["total"] == 0


def test_phase_default_output_preserves_shipped_evidence(tmp_path, monkeypatch):
    from scripts import backend_phase_http

    evidence = backend_phase_http.ROOT / "docs/backend-phase-http.json"
    before = hashlib.sha256(evidence.read_bytes()).hexdigest()
    monkeypatch.setattr(
        backend_phase_http, "run", lambda: {"passed": True, "scope": "FAKE output-path unit test"}
    )
    backend_phase_http.main([])
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == before
    target = tmp_path / "result.json"
    backend_phase_http.main(["--output", str(target)])
    assert target.is_file()


def test_epoch_rotation_blocks_pruned_create_and_old_reset_replays(api, monkeypatch):
    """Accelerated retention cap, with all writes performed through real API handlers."""
    client, app = api
    monkeypatch.setattr(app.state.repo, "RECEIPT_LIMIT", 3)
    original = {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "personal_name": "private original",
        "location": "drawer",
    }
    item = client.post("/api/items", json=original).json()["items"][0]
    deletion = mutation(item, evidence_scope="all_affected")
    assert client.request("DELETE", f"/api/items/{item['id']}", json=deletion).status_code == 200
    manual(client, name="survivor one")
    manual(client, name="survivor two")  # fourth receipt rotates to epoch 1
    assert client.get("/api/status").json()["write_epoch"] == 1
    assert client.post("/api/items", json=original).status_code == 409
    assert client.request("DELETE", f"/api/items/{item['id']}", json=deletion).status_code == 404
    manual(client, name="fresh work", write_epoch=1)
    reset = {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "confirmation": "DELETE ALL LOCAL DATA",
        "expected_generation": client.get("/api/status").json()["generation"],
    }
    assert client.request("DELETE", "/api/data", json=reset).status_code == 200
    assert client.post("/api/items", json=original).status_code == 409
    for i in range(4):
        epoch = client.get("/api/status").json()["write_epoch"]
        manual(client, name=f"after reset {i}", write_epoch=epoch)
    # Old delete-all receipt has been pruned; its old generation cannot delete new records.
    assert client.request("DELETE", "/api/data", json=reset).status_code == 409
    assert client.get("/api/items").json()["total"] == 4
    assert client.post("/api/items", json=original).status_code == 409
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM receipts").fetchone()[0] <= 3


def test_existing_photo_stale_revision_preserves_metadata(api):
    client, _ = api
    item = manual(client, aliases=["safe alias"])
    changed = client.patch(
        f"/api/items/{item['id']}", json=mutation(item, distinguishing_note="new note")
    ).json()["items"][0]
    draft = upload(client)
    payload = commit_payload(
        rows=[
            {
                "identity": "existing",
                "item_id": item["id"],
                "expected_revision": item["revision"],
                "personal_name": item["personal_name"],
                "aliases": [],
            }
        ]
    )
    response = client.post(f"/api/captures/{draft['id']}/commit", json=payload)
    assert response.status_code == 409
    assert client.get(f"/api/items/{item['id']}").json() == changed


def test_guard_words_in_exact_alias_stay_ambiguous(api):
    client, _ = api
    manual(client, name="red poster", aliases=["do not disturb sign"])
    manual(client, name="blue poster", aliases=["do not disturb sign"])
    assert recall(client, "where is my do not disturb sign?")["kind"] == "clarify"
    assert recall(client, "where is my sign not red?")["kind"] == "unknown"


def test_locked_database_does_not_stall_event_loop_cancel(api):
    import asyncio
    import threading
    import time

    from app.contracts import Recall
    from app.errors import AppError

    _, app = api
    held = threading.Event()
    release = threading.Event()

    def writer():
        with app.state.repo.db.lock:
            held.set()
            release.wait(0.5)

    thread = threading.Thread(target=writer)
    thread.start()
    assert held.wait(1)

    async def scenario():
        stop = asyncio.Event()
        start = time.monotonic()
        ticks = []

        async def cancel():
            await asyncio.sleep(0.02)
            ticks.append(time.monotonic() - start)
            stop.set()
            release.set()

        heartbeat = asyncio.create_task(cancel())
        with pytest.raises(AppError) as error:
            await app.state.recall.recall(Recall(query="keys", request_id=str(uuid4())), stop, 0)
        await heartbeat
        assert error.value.code == "request_cancelled"
        assert ticks[0] < 0.25, "database lock stalled cancellation on event loop"

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        thread.join(1)


def test_overdue_import_still_requires_recheck():
    from app.freshness import freshness

    observation = {
        "location_state": "recorded",
        "confirmed_at": "2020-01-01T00:00:00+00:00",
        "review_after": "2020-01-02T00:00:00+00:00",
    }
    assert (
        freshness(observation, {"captured_at": None}, "2020-01-01T00:00:00+00:00")
        == "needs_recheck"
    )
