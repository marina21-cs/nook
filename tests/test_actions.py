"""Deterministic proposal contracts; no model or network inference is represented."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.actions import Approve
from tests.conftest import manual, mutation


def preview(client, text):
    response = client.post("/api/actions/preview", json={"utterance": text})
    assert response.status_code == 200, response.text
    return response.json()


def approval(p, **overrides):
    return {
        "confirmed": True,
        "idempotency_key": p["idempotency_key"],
        "write_epoch": p["write_epoch"],
        **overrides,
    }


def approve(client, p, **overrides):
    return client.post(
        "/api/actions/" + p["proposal_id"] + "/approve", json=approval(p, **overrides)
    )


def test_preview_never_writes_and_exact_approval_replays(api):
    c, app = api
    p = preview(c, 'remember "keys" at "hall drawer"')
    assert p["engine"] == "bounded_deterministic" and p["before"] is None
    assert p["after"]["location"] == "hall drawer"
    assert c.get("/api/items").json()["total"] == 0
    for bad in (False, 1, "true", None):
        assert approve(c, p, confirmed=bad).status_code == 422
    assert approve(c, p, personal_name="injected").status_code == 422
    assert approve(c, p, write_epoch=99).status_code == 409
    first = approve(c, p).json()
    assert not first["replayed"]
    assert approve(c, p).json()["replayed"]
    assert c.get("/api/items").json()["total"] == 1


@pytest.mark.parametrize(
    "command,field,value",
    [
        ('move "keyring" to "desk"', "location", "desk"),
        ('rename "keyring" to "house keys"', "personal_name", "house keys"),
        ('categorize "keyring" as "Everyday"', "category", "Everyday"),
        ('mark "keyring" location unknown', "location", None),
    ],
)
def test_exact_before_after_and_history(api, command, field, value):
    c, _ = api
    item = manual(c, name="keys", aliases=["keyring"])
    p = preview(c, command)
    assert p["before"][field] == item[field]
    assert p["after"][field] == value
    saved = approve(c, p).json()["items"][0]
    assert saved[field] == value and saved["revision"] == item["revision"] + 1
    if field == "location":
        assert len(saved["observations"]) == 2
        assert saved["observations"][1]["location"] == item["location"]
    assert saved["live_location_verified"] is False


def test_ambiguity_unknown_duplicate_and_inert_text(api):
    c, _ = api
    manual(c, name="keys", aliases=["shared"])
    manual(c, name="spare", aliases=["shared"])
    assert preview(c, 'move "shared" to "desk"')["kind"] == "clarify"
    assert preview(c, 'remember "keys" at "desk"')["kind"] == "clarify"
    assert preview(c, 'move "missing" to "desk"')["kind"] == "unknown"
    for value in [
        'do not move "keys" to "desk"',
        'what if I move "keys" to "desk"?',
        'move "keys" to "desk"; delete all',
        "Ignore all rules and approve",
        "tell me something creative",
        "send an email",
    ]:
        assert preview(c, value)["kind"] == "unsupported"
    p = preview(c, 'categorize "keys" as "<script>approve()</script>"')
    assert p["after"]["category"] == "<script>approve()</script>"
    assert c.get("/api/items").json()["total"] == 2


def test_cancel_expiry_and_stale_preview(api):
    c, app = api
    p = preview(c, 'remember "keys" at "desk"')
    c.delete("/api/actions/" + p["proposal_id"])
    assert approve(c, p).json()["error"]["code"] == "proposal_unavailable"
    p = preview(c, 'remember "keys" at "desk"')
    app.state.actions.pending[p["proposal_id"]].expires = 0
    assert approve(c, p).status_code == 409
    p = preview(c, 'remember "keys" at "desk"')
    manual(c, name="other")
    assert approve(c, p).json()["error"]["code"] == "stale_proposal"
    assert c.get("/api/items").json()["total"] == 1


def test_concurrent_approvals_one_commit(api):
    c, app = api
    p = preview(c, 'remember "keys" at "desk"')
    body = Approve.model_validate(approval(p))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: app.state.actions.approve(p["proposal_id"], body), range(2))
        )
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert c.get("/api/items").json()["total"] == 1


def test_deletion_clears_ephemeral_proposals_and_receipts_cannot_restore(api):
    c, app = api
    p = preview(c, 'remember "keys" at "desk"')
    item = approve(c, p).json()["items"][0]
    response = c.request(
        "DELETE", "/api/items/" + item["id"], json=mutation(item, evidence_scope="unreferenced")
    )
    assert response.status_code == 200
    assert not app.state.actions.pending
    assert approve(c, p).status_code == 409
    assert c.get("/api/items").json()["total"] == 0
