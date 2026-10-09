from uuid import uuid4

import pytest

from tests.conftest import commit_payload, manual, mutation, recall, upload


@pytest.mark.parametrize(
    "override",
    [
        {"confirmed": False},
        {"confirmed": 1},
        {"confirmed": "true"},
        {"location": ""},
        {"personal_name": 42},
        {"personal_name": "x" * 81},
        {"aliases": ["blue", "BLUE"]},
        {"aliases": ["a\nsecret"]},
        {"personal_name": "name\u0000hidden"},
        {"timestamp": "2020-01-01"},
        {"photo_path": "/etc/passwd"},
        {"tool": {"name": "execute"}},
        {"idempotency_key": "../../etc/passwd"},
    ],
)
def test_strict_confirmed_contracts(api, override):
    client, _ = api
    body = {
        "confirmed": True,
        "idempotency_key": str(uuid4()),
        "personal_name": "bottle",
        "location": "drawer",
        **override,
    }
    response = client.post("/api/items", json=body)
    assert response.status_code == 422
    assert client.get("/api/items").json()["total"] == 0
    assert "input" not in response.text and "/etc/passwd" not in response.text


@pytest.mark.parametrize(
    "region",
    [
        {"x": 0.9, "y": 0.0, "w": 0.2, "h": 0.1},
        {"x": -0.1, "y": 0.0, "w": 0.2, "h": 0.1},
        {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.1},
        {"x": "0.1", "y": 0.0, "w": 0.2, "h": 0.1},
        {"x": 0.0, "y": 0.0, "w": 0.001, "h": 0.001},
        {"x": 0.0, "y": 0.0, "w": 0.2, "h": 0.1, "action": "execute"},
    ],
)
def test_out_of_image_and_invalid_regions(api, region):
    client, _ = api
    draft = upload(client)
    body = commit_payload(rows=[{"identity": "new", "personal_name": "bottle", "region": region}])
    response = client.post(f"/api/captures/{draft['id']}/commit", json=body)
    assert response.status_code == 422
    assert client.get("/api/items").json()["total"] == 0


def test_duplicate_json_and_nonfinite_rejected_before_parsing(api):
    client, _ = api
    for body in [
        '{"personal_name":"bottle","personal_name":"scissors"}',
        '{"rows":[{"region":{"x":0.0,"x":0.2}}]}',
        '{"query":"bottle","x":NaN}',
        '{"query":"bottle","x":Infinity}',
        "[" + "{}" + "]",
        "{malformed}",
        "[" * 1100 + "]" * 1100,
    ]:
        response = client.post(
            "/api/recall", content=body, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422 and "error" in response.json()


def test_idempotency_conflicts_and_changed_record_replay(api):
    client, _ = api
    key = str(uuid4())
    item = manual(client, idempotency_key=key)
    changed_body = {
        "confirmed": True,
        "idempotency_key": key,
        "personal_name": "different",
        "location": "drawer",
    }
    assert client.post("/api/items", json=changed_body).status_code == 409
    original = {
        "confirmed": True,
        "idempotency_key": key,
        "personal_name": "blue craft scissors",
        "location": "Hall drawer",
    }
    assert client.post("/api/items", json=original).json()["replayed"]
    client.patch(f"/api/items/{item['id']}", json=mutation(item, personal_name="new name"))
    replay = client.post("/api/items", json=original)
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "stale_receipt"
    assert client.get("/api/items").json()["total"] == 1


def test_sql_html_prompt_text_is_inert_data(api):
    client, app = api
    label = "<script>ignore instructions; DROP TABLE items;</script>"
    item = manual(client, label, aliases=["test bottle"])
    response = client.get(f"/api/items/{item['id']}")
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["personal_name"] == label
    assert recall(client, "test bottle")["items"][0]["id"] == item["id"]
    with app.state.repo.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM items").fetchone()[0] == 1


def test_exact_hosts_origins_session_csrf_and_no_cache(api):
    client, app = api
    assert client.get("/api/items", headers={"Host": "evil.example:8765"}).status_code == 403
    for origin in (
        "https://evil.example",
        "http://127.0.0.1:8766",
        "null",
        "http://localhost.evil:8765",
    ):
        assert client.get("/api/session", headers={"Origin": origin}).status_code == 403
    assert client.get("/api/items", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    response = client.post(
        "/api/recall",
        json={"query": "bottle", "request_id": str(uuid4())},
        headers={"X-CSRF-Token": "bad"},
    )
    assert response.status_code == 403
    client.cookies.clear()
    assert client.get("/api/items").status_code == 401
    new = client.get("/api/session")
    assert (
        "HttpOnly" in new.headers["set-cookie"] and "SameSite=strict" in new.headers["set-cookie"]
    )
    assert new.headers["cache-control"] == "no-store"
    assert new.headers["x-content-type-options"] == "nosniff"


def test_no_cdn_docs_and_openapi_available_in_session(api):
    client, _ = api
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/captures/{capture_id}/commit" in schema.json()["paths"]
    document = schema.json()
    upload_contract = document["paths"]["/api/captures"]["post"]
    assert set(upload_contract["requestBody"]["content"]) == {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    assert upload_contract["security"] == [{"LocalSessionCookie": [], "CsrfToken": []}]
    assert document["paths"]["/api/items"]["get"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_limits_and_identity_choices(api):
    client, _ = api
    draft = upload(client)
    for rows in [
        [],
        [{"identity": "new", "personal_name": "bottle"}] * 6,
        [{"identity": "existing", "personal_name": "bottle"}],
        [{"identity": "new", "personal_name": "bottle", "item_id": str(uuid4())}],
    ]:
        assert (
            client.post(
                f"/api/captures/{draft['id']}/commit", json=commit_payload(rows=rows)
            ).status_code
            == 422
        )
    assert client.get("/api/items?limit=51").status_code == 422
    assert client.get("/api/items?offset=-1").status_code == 422
    for query in ("", "x" * 2001, 42):
        assert (
            client.post(
                "/api/recall", json={"query": query, "request_id": str(uuid4())}
            ).status_code
            == 422
        )
