"""Deterministic parser/HTTP regressions; speech providers disabled, no inference."""

from uuid import uuid4

import pytest

from tests.conftest import manual, recall


@pytest.mark.parametrize(
    "name,alias",
    [
        ("blue keys", "house keyring"),
        ("teal travel pouch", "weekend bag"),
        ("brass cabinet tool", "workshop opener"),
    ],
)
@pytest.mark.parametrize(
    "template,use_alias",
    [
        ("Where are my {}?", False),
        ("Where are my {}?", True),
        ("Where is the {}?", True),
        ("Where did I put my {}?", False),
    ],
)
def test_natural_questions_recall_arbitrary_names_and_aliases(
    api, name, alias, template, use_alias
):
    client, app = api
    item = manual(client, name, aliases=[alias], location="Test shelf")
    manual(client, "other unrelated object", location="Other shelf")
    generation = app.state.repo.generation()
    query = template.format(alias if use_alias else name)
    direct = recall(client, query)
    assert direct["kind"] == "found" and direct["items"][0]["id"] == item["id"]
    assert not direct["inference_used"]
    spoken = client.post(
        "/api/speech/turns",
        json={"request_id": str(uuid4()), "utterance": query, "transcript_confirmed": True},
    )
    assert spoken.status_code == 200, spoken.text
    assert spoken.json()["kind"] == "memory"
    assert spoken.json()["recall"]["items"][0]["id"] == item["id"]
    assert spoken.json()["speech"]["status"] == "not_provisioned"
    assert app.state.repo.generation() == generation
    assert app.state.repo.get(item["id"]) == item


def test_shared_alias_natural_question_requires_disambiguation(api):
    client, app = api
    first = manual(client, "silver badge", aliases=["studio tags"])
    second = manual(client, "orange fob", aliases=["studio tags"])
    generation = app.state.repo.generation()
    result = recall(client, "Where are my studio tags?")
    assert result["kind"] == "clarify" and result["total"] == 2
    assert {row["id"] for row in result["items"]} == {first["id"], second["id"]}
    assert app.state.repo.generation() == generation


def test_verified_descriptive_transcript_is_not_silently_rewritten_to_question(api):
    client, app = api
    item = manual(client, "blue keys", location="Desk drawer")
    generation = app.state.repo.generation()
    description = (
        "Blue Keys last recorded at Desk drawer on October 9, 2026. Current location is unverified."
    )
    result = recall(client, description)
    assert result["kind"] == "unknown" and result["reason"] == "no_confirmed_match"
    assert result["items"] == [] and not result["inference_used"]
    assert recall(client, "Where are my blue keys?")["items"][0]["id"] == item["id"]
    assert app.state.repo.generation() == generation
    assert app.state.repo.get(item["id"]) == item
