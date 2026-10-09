import asyncio
import re
import time
from typing import Any

from app.contracts import Recall
from app.errors import AppError
from app.inference.text import TextAdapter
from app.item_repository import ItemRepository
from app.language import FIL_NEGATION, recall_query

STOP = set(
    "where did do i put my the is are a an please find locate last recorded in at this that can you tell me keep kept store stored saved have has was were to of it for whats what s item's item items remember placed leave left about".split()
)
NEGATION = {"not", "without", "except", "excluding", "never", "dont"}
ACTION = {
    "execute",
    "shell",
    "sudo",
    "delete",
    "erase",
    "download",
    "upload",
    "http",
    "https",
    "ignore",
    "instructions",
}


def words(value: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))


def keywords(value: str) -> set[str]:
    # Remove a query phrase, rather than treating 'place' as a universal stop word.
    # This keeps distinguishing item words and names intact.
    value = re.sub(r"\blast\s+recorded\s+(place|location)\b", "", value, flags=re.IGNORECASE)
    return words(value) - STOP


def exact_labels(items: list[dict], query: str) -> list[dict]:
    """Only a whole confirmed label or a complete recall wrapper bypasses word guards."""
    query, _ = recall_query(query)
    query = re.sub(
        r"^(?:where\s+(?:is|are)\s+(?:(?:my|the)\s+)?|where\s+did\s+i\s+put\s+(?:my\s+)?)",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    )

    def normalize(value: str) -> str:
        return " ".join(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))

    wanted = normalize(query)
    return [
        item
        for item in items
        if wanted
        and any(normalize(label) == wanted for label in [item["personal_name"], *item["aliases"]])
    ]


def matches(items: list[dict], query: str, terms: list[str] | None = None) -> list[dict]:
    query, _ = recall_query(query)
    needed = keywords(query)
    if not needed:
        return []
    found = []
    for item in items:
        labels = [item["personal_name"], *item["aliases"]]
        searchable = keywords(
            " ".join([*labels, item["distinguishing_note"], item["category"] or ""])
        )
        exact = any(keywords(label) == needed for label in labels)
        original = needed <= searchable
        expanded = any(
            needed <= keywords(term) and keywords(term) <= searchable for term in terms or []
        )
        if original or expanded:
            found.append((int(exact), item))
    # Ranking orders candidates; it never collapses all plausible matches to one.
    found.sort(key=lambda pair: (-pair[0], pair[1]["personal_name"].casefold(), pair[1]["id"]))
    return [item for _, item in found]


class RecallService:
    def __init__(self, repository: ItemRepository, text: TextAdapter) -> None:
        self.repo = repository
        self.text = text

    async def recall(self, request: Recall, cancelled: Any, generation: int) -> dict:
        start = time.monotonic()
        query, _ = recall_query(request.query)
        query_words = words(request.query)
        unsupported = bool(query_words & (NEGATION | ACTION | FIL_NEGATION))
        outcome: dict[str, Any] = {
            "terms": [],
            "inference_status": "not_requested",
            "inference_used": False,
            "fallback_used": False,
            "repair_used": False,
        }
        if request.use_inference and not unsupported:
            outcome = await self.text.normalize(query, cancelled)
        result = await asyncio.to_thread(
            self._read_result, request, cancelled, generation, start, query, unsupported, outcome
        )
        if cancelled.is_set():
            raise AppError(409, "request_cancelled", "Request cancelled; its result was discarded.")
        return result

    def _read_result(
        self,
        request: Recall,
        cancelled: Any,
        generation: int,
        start: float,
        query: str,
        unsupported: bool,
        outcome: dict[str, Any],
    ) -> dict:
        with self.repo.db.lock, self.repo.db.connect() as conn:
            if cancelled.is_set():
                raise AppError(
                    409, "request_cancelled", "Request was cancelled; its result was discarded."
                )
            if self.repo.db.generation(conn) != generation:
                raise AppError(
                    409,
                    "stale_request",
                    "Collection changed while searching. Retry with a new request ID.",
                )
            items = self.repo.all(conn)
            literal = exact_labels(items, request.query) if unsupported else []
            if literal:
                unsupported = False
            results = literal or ([] if unsupported else matches(items, query, outcome["terms"]))
            kind = "unknown" if not results else "found" if len(results) == 1 else "clarify"
            reason = (
                "unsupported_query"
                if unsupported
                else "no_confirmed_match"
                if not results
                else "multiple_confirmed_matches"
                if len(results) > 1
                else "last_recorded_evidence"
            )
            if len(results) == 1 and results[0]["location"] is None:
                kind, reason = "unknown", "location_unknown"
            return {
                "kind": kind,
                "request_id": str(request.request_id),
                "items": results[:5],
                "total": len(results),
                "generation": generation,
                "reason": reason,
                **{k: v for k, v in outcome.items() if k != "terms"},
                "elapsed_ms": round((time.monotonic() - start) * 1000, 2),
            }
