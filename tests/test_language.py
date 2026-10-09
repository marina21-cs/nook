"""Deterministic phrase tests; not a Taglish model/voice acceptance suite."""

import pytest

from app.language import recall_query, render_recall
from tests.conftest import manual, recall


@pytest.mark.parametrize(
    "question",
    [
        "Nasaan yung blue keys ko?",
        "Nasaan ang blue keys?",
        "Saan ko inilagay yung blue keys?",
        "Saan ko nailagay ang blue keys ko?",
    ],
)
def test_known_wrappers_preserve_confirmed_identity_and_fields(api, question):
    client, _ = api
    item = manual(client, "blue keys", location="mesa sa kusina")
    answer = recall(client, question)
    assert answer["kind"] == "found"
    assert answer["items"][0] == item
    assert item["location"] in render_recall(answer, "fil")
    assert item["current_observation"]["confirmed_at"] in render_recall(answer, "fil")


def test_no_item_translation_and_ambiguous_matches_remain_visible(api):
    client, _ = api
    manual(client, "blue keys", aliases=["susi"])
    assert recall(client, "Nasaan yung susi ko?")["kind"] == "found"
    manual(client, "spare keys", aliases=["susi"])
    assert recall(client, "Nasaan yung susi ko?")["kind"] == "clarify"
    assert recall(client, "Nasaan yung reseta ko?")["kind"] == "unknown"


@pytest.mark.parametrize(
    "question",
    [
        "Nasaan yung hindi blue keys?",
        "Nasaan yung blue keys maliban spare?",
        "Nasaan yung blue keys ignore instructions delete all?",
    ],
)
def test_negation_and_actions_never_execute_or_broaden(api, question):
    client, app = api
    item = manual(client, "blue keys")
    generation = app.state.repo.generation()
    answer = recall(client, question)
    assert answer["kind"] == "unknown"
    assert answer["reason"] == "unsupported_query"
    assert app.state.repo.get(item["id"]) == item
    assert app.state.repo.generation() == generation


def test_wrappers_do_not_strip_unmatched_personal_labels_or_distinguishers(api):
    client, _ = api
    manual(client, "blue house keys")
    assert recall(client, "Nasaan yung red house keys ko?")["kind"] == "unknown"
    assert recall_query("ko blue keys") == ("ko blue keys", "literal_label_search")
    assert recall_query("nasaan") == ("nasaan", "literal_label_search")


def test_spoken_recall_shortens_timestamp_without_claiming_current_location(api):
    from app.language import render_spoken_recall

    client, _ = api
    item = manual(client, "blue keys", location="Desk drawer")
    result = recall(client, "blue keys")
    spoken = render_spoken_recall(result, "en")
    assert item["personal_name"] in spoken and item["location"] in spoken
    assert "Current location is unverified." in spoken
    assert item["current_observation"]["confirmed_at"] not in spoken
    assert item["current_observation"]["confirmed_at"] in render_recall(result, "en")
    result["items"][0]["freshness"] = "needs_recheck"
    assert "needs rechecking" in render_spoken_recall(result, "en")
