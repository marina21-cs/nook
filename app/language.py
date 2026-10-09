"""Conservative recall wrappers, not translation or general language inference."""

import re
from datetime import datetime
from typing import Any

# Only remove a complete known question prefix. Personal labels remain literal.
FIL_PREFIX = re.compile(
    r"^(?:nasaan|nasan|saan\s+ko\s+(?:inilagay|nilagay|nailagay|itinago|naiwan))"
    r"\s+(?:(?:ang|yung|iyong)\s+)?(?P<label>.+?)\s*[?？.!]*$",
    re.IGNORECASE,
)
FIL_NEGATION = {"hindi", "huwag", "wag", "wala", "maliban"}


def recall_query(query: str) -> tuple[str, str]:
    value = query.strip()
    found = FIL_PREFIX.fullmatch(value)
    if not found:
        return query, "literal_label_search"
    label = found.group("label").strip().rstrip("?？.!").strip()
    # Possession is removed only inside the recognized recall question.
    label = re.sub(r"\s+ko$", "", label, flags=re.IGNORECASE).strip()
    return label, "filipino_recall_wrapper"


def render_recall(result: dict[str, Any], language: str) -> str:
    """Narrate authoritative fields without modifying or inferring them."""
    fil = language == "fil"
    if result["kind"] == "clarify":
        return (
            "Aling naitalang item ang ibig mong sabihin?"
            if fil
            else "Which recorded item do you mean?"
        )
    if result["kind"] != "found":
        return (
            "Walang tiyak na naitalang lokasyon para sa item na ito."
            if fil
            else "I do not have a confirmed recorded location for that item."
        )
    item = result["items"][0]
    observation = item["current_observation"]
    when = observation["confirmed_at"]
    name, location = item["personal_name"], item["location"]
    text = (
        f"Huling naitala: {name} — {location} ({when}). Hindi kumpirmado ang kasalukuyang lokasyon."
        if fil
        else f"Last recorded: {name} — {location} ({when}). Its current location is unverified."
    )
    if item["freshness"] == "needs_recheck":
        text += " Kailangang tingnan muli ang tala." if fil else "This record needs rechecking."
    return text


def render_spoken_recall(result: dict[str, Any], language: str) -> str:
    """Brief English narration; the complete timestamp remains in the text and record."""
    if language not in {"en", "auto"} or result["kind"] != "found":
        return render_recall(result, language)
    item = result["items"][0]
    when = datetime.fromisoformat(item["current_observation"]["confirmed_at"])
    date = when.strftime("%B %d, %Y")
    text = f"{item['personal_name']}: last recorded at {item['location']} on {date}. Current location is unverified."
    if item["freshness"] == "needs_recheck":
        text += " This record needs rechecking."
    return text
