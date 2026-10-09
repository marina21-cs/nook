from uuid import uuid4

from tests.conftest import captured, manual, mutation, recall, upload


def test_shared_evidence_deletion_preserves_other_record_with_clear_scope(api):
    client, app = api
    first, second = captured(client, names=("blue scissors", "red bottle"))
    photo = first["current_observation"]["photo"]
    preview = client.get(f"/api/items/{first['id']}/deletion-preview").json()
    assert preview["shared_with_item_ids"] == [second["id"]] and preview["warning"]
    upload(client)
    body = mutation(first, evidence_scope="unreferenced")
    deleted = client.request("DELETE", f"/api/items/{first['id']}", json=body)
    assert deleted.status_code == 200 and deleted.json()["shared_pixels_retained"]
    assert client.request("DELETE", f"/api/items/{first['id']}", json=body).json()["replayed"]
    assert recall(client, "blue scissors")["kind"] == "unknown"
    assert client.get(photo["url"]).status_code == 200
    assert client.get(f"/api/items/{second['id']}").json() == second
    assert not list(app.state.store.drafts.iterdir())
    assert b"blue scissors" not in app.state.repo.db.path.read_bytes()


def test_all_affected_removes_pixels_and_bumps_surviving_revision(api):
    client, app = api
    first, second = captured(client, names=("blue scissors", "red bottle"))
    photo = first["current_observation"]["photo"]
    result = client.request(
        "DELETE", f"/api/items/{first['id']}", json=mutation(first, evidence_scope="all_affected")
    )
    assert result.status_code == 200 and not result.json()["shared_pixels_retained"]
    assert result.json()["affected_item_count"] == 1
    survivor = client.get(f"/api/items/{second['id']}").json()
    assert survivor["revision"] == second["revision"] + 1
    assert survivor["location"] == second["location"]
    assert survivor["current_observation"]["photo"] is None
    assert survivor["current_observation"]["evidence_status"] == "removed"
    assert client.get(photo["url"]).status_code == 404
    assert not list(app.state.store.photos.iterdir())


def test_unreferenced_photo_removed_and_no_deleted_retrieval(api):
    client, app = api
    item = captured(client)[0]
    photo = item["current_observation"]["photo"]
    result = client.request(
        "DELETE", f"/api/items/{item['id']}", json=mutation(item, evidence_scope="unreferenced")
    )
    assert result.status_code == 200
    assert recall(client)["kind"] == "unknown"
    assert client.get(photo["url"]).status_code == 404
    assert client.get(f"/api/items/{item['id']}").status_code == 404
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM photos").fetchone()[0] == 0
    assert not list(app.state.store.photos.iterdir())


def test_delete_all_replaces_database_and_retry_never_erases_new_records(api):
    client, app = api
    captured(client)
    upload(client)
    untouched = app.state.store.root / "unrelated.txt"
    untouched.write_text("not an app asset")
    generation = client.get("/api/items").json()["generation"]
    inode = app.state.repo.db.path.stat().st_ino
    body = {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "confirmation": "DELETE ALL LOCAL DATA",
        "expected_generation": generation,
    }
    result = client.request("DELETE", "/api/data", json=body)
    assert result.status_code == 200
    assert app.state.repo.db.path.stat().st_ino != inode
    assert client.get("/api/items").json()["total"] == 0
    assert not list(app.state.store.photos.iterdir()) and not list(app.state.store.drafts.iterdir())
    assert untouched.read_text() == "not an app asset"
    assert b"blue craft scissors" not in app.state.repo.db.path.read_bytes()
    item = manual(client, "new bottle", write_epoch=result.json()["write_epoch"])
    repeated = client.request("DELETE", "/api/data", json=body)
    assert repeated.status_code == 200 and repeated.json()["replayed"]
    assert client.get(f"/api/items/{item['id']}").status_code == 200


def test_delete_confirmations_and_stale_generation(api):
    client, _ = api
    item = manual(client)
    bad = client.request("DELETE", f"/api/items/{item['id']}", json=mutation(item))
    assert bad.status_code == 422
    bad = client.request(
        "DELETE",
        "/api/data",
        json={
            "confirmed": True,
            "idempotency_key": str(uuid4()),
            "confirmation": "DELETE ALL LOCAL DATA",
            "expected_generation": 0,
        },
    )
    assert bad.status_code == 409
    assert client.get(f"/api/items/{item['id']}").status_code == 200
