"""Ephemeral, deterministic proposals. Text can propose; only an approval can write."""

import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.contracts import AddObservation, Confirmed, Contract, Edit, ManualCreate, Query
from app.errors import AppError
from app.item_repository import ItemRepository

router = APIRouter(prefix="/api/actions")
EXAMPLES = [
    'remember "keys" at "hall drawer"',
    'move "keys" to "desk"',
    'rename "keys" to "house keys"',
    'categorize "keys" as "Everyday"',
    'mark "keys" location unknown',
]
# Deliberately anchored and quoted: no instruction extraction from prose or stored data.
PATTERNS = [
    ("remember", r'remember "([^"\n]+)" at "([^"\n]+)"'),
    ("move", r'move "([^"\n]+)" to "([^"\n]+)"'),
    ("rename", r'rename "([^"\n]+)" to "([^"\n]+)"'),
    ("category", r'categorize "([^"\n]+)" as "([^"\n]+)"'),
    ("unknown", r'mark "([^"\n]+)" location unknown'),
]


class Preview(Contract):
    utterance: Query


class Approve(Confirmed):
    pass


@dataclass
class Proposal:
    expires: float
    generation: int
    operation: str
    item_id: str | None
    body: ManualCreate | Edit | AddObservation


class Actions:
    TTL = 300
    LIMIT = 64

    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo
        self.pending: dict[str, Proposal] = {}

    def prune(self) -> None:
        self.pending = {k: v for k, v in self.pending.items() if v.expires > time.monotonic()}

    def clear(self) -> None:
        with self.repo.db.lock:
            self.pending.clear()

    def preview(self, utterance: str) -> dict[str, Any]:
        common = {
            "engine": "bounded_deterministic",
            "inference_used": False,
            "saved": False,
            "approval_required": True,
            "examples": EXAMPLES,
        }
        parsed = next(
            (
                (op, m)
                for op, pattern in PATTERNS
                if (m := re.fullmatch(pattern, utterance.strip(), re.IGNORECASE))
            ),
            None,
        )
        if parsed is None:
            return {
                **common,
                "kind": "unsupported",
                "reason": "Use one quoted command from the examples. No change was made.",
            }
        operation, match = parsed
        name = match[1].strip()
        value = match[2].strip() if operation != "unknown" else None
        with self.repo.db.lock, self.repo.db.connect() as conn:
            self.prune()
            generation = self.repo.db.generation(conn)
            epoch = self.repo.write_epoch(conn)
            items = self.repo.all(conn)
            found = [
                i
                for i in items
                if name.casefold() in {n.casefold() for n in [i["personal_name"], *i["aliases"]]}
            ]
            if operation == "remember" and found:
                return {
                    **common,
                    "kind": "clarify",
                    "reason": "That name or alias already exists. Use Remember to explicitly choose an existing or separate item.",
                    "items": [
                        {
                            "id": i["id"],
                            "personal_name": i["personal_name"],
                            "location": i["location"],
                        }
                        for i in found
                    ],
                }
            if operation != "remember" and len(found) != 1:
                return {
                    **common,
                    "kind": "clarify" if found else "unknown",
                    "reason": "Choose an exact, unique saved name or alias. No change was made.",
                    "items": [
                        {
                            "id": i["id"],
                            "personal_name": i["personal_name"],
                            "location": i["location"],
                        }
                        for i in found
                    ],
                }
            item = found[0] if found else None
            before = (
                {
                    k: item[k]
                    for k in (
                        "id",
                        "revision",
                        "personal_name",
                        "aliases",
                        "distinguishing_note",
                        "category",
                        "location",
                    )
                }
                if item
                else None
            )
            identifier = str(uuid4())
            base: dict[str, Any] = {
                "confirmed": True,
                "idempotency_key": UUID(identifier),
                "write_epoch": epoch,
            }
            body: ManualCreate | Edit | AddObservation
            try:
                if operation == "remember":
                    body = ManualCreate.model_validate(
                        {**base, "personal_name": name, "location": value}
                    )
                    after: dict[str, Any] = {
                        "personal_name": body.personal_name,
                        "aliases": [],
                        "distinguishing_note": "",
                        "category": None,
                        "location": body.location,
                    }
                else:
                    assert item is not None and before is not None
                    base["expected_revision"] = item["revision"]
                    after = dict(before)
                    if operation in {"move", "unknown"}:
                        body = AddObservation.model_validate({**base, "location": value})
                        after["location"] = body.location
                    else:
                        field = "personal_name" if operation == "rename" else "category"
                        body = Edit.model_validate({**base, field: value})
                        after[field] = getattr(body, field)
                    after["revision"] = item["revision"] + 1
            except ValidationError as exc:
                raise AppError(
                    422,
                    "invalid_action",
                    "The proposed name, category or location exceeds the record limits.",
                ) from exc
            if len(self.pending) >= self.LIMIT:
                raise AppError(
                    429, "proposal_limit", "Cancel a pending proposal or wait for it to expire."
                )
            self.pending[identifier] = Proposal(
                time.monotonic() + self.TTL,
                generation,
                operation,
                item["id"] if item else None,
                body,
            )
            return {
                **common,
                "kind": "proposal",
                "proposal_id": identifier,
                "operation": operation,
                "before": before,
                "after": after,
                "expected_generation": generation,
                "write_epoch": epoch,
                "idempotency_key": identifier,
                "expires_in_seconds": self.TTL,
                "effect": "Save a user-reported record only; no physical action or live location verification.",
            }

    def approve(self, identifier: str, approval: Approve) -> dict:
        with self.repo.db.lock:
            self.prune()
            proposal = self.pending.get(identifier)
            if proposal is None:
                raise AppError(
                    409,
                    "proposal_unavailable",
                    "Proposal expired, was cancelled, or predates a server restart. Review a new proposal.",
                )
            if (
                approval.idempotency_key != proposal.body.idempotency_key
                or approval.write_epoch != proposal.body.write_epoch
            ):
                raise AppError(
                    409,
                    "proposal_mismatch",
                    "Approval must use the exact proposal key and write epoch.",
                )
            op = (
                "manual_create"
                if proposal.operation == "remember"
                else f"observe:{proposal.item_id}"
                if proposal.operation in {"move", "unknown"}
                else f"edit:{proposal.item_id}"
            )
            with self.repo.db.connect() as conn:
                # Receipt first makes an uncertain successful approval safely retryable.
                previous = self.repo.receipt(
                    conn,
                    op,
                    identifier,
                    self.repo.fingerprint(op, self.repo.request_payload(proposal.body)),
                    approval.write_epoch,
                )
                if previous is not None:
                    return previous
                if self.repo.db.generation(conn) != proposal.generation:
                    raise AppError(
                        409,
                        "stale_proposal",
                        "Records changed after this preview. Review a new proposal.",
                    )
            # The RLock also serializes direct writes, cancellation and deletions.
            if isinstance(proposal.body, ManualCreate):
                return self.repo.create_manual(proposal.body)
            assert proposal.item_id is not None
            if isinstance(proposal.body, Edit):
                return self.repo.edit(proposal.item_id, proposal.body)
            return self.repo.add_observation(proposal.item_id, proposal.body)

    def cancel(self, identifier: str) -> dict:
        with self.repo.db.lock:
            self.pending.pop(identifier, None)
        return {"cancelled": True, "committed_changes_undone": False}


@router.post("/preview")
def preview(body: Preview, request: Request) -> dict:
    return request.app.state.actions.preview(body.utterance)


@router.post("/{proposal_id}/approve")
def approve(proposal_id: UUID, body: Approve, request: Request) -> dict:
    return request.app.state.actions.approve(str(proposal_id), body)


@router.delete("/{proposal_id}")
def cancel(proposal_id: UUID, request: Request) -> dict:
    return request.app.state.actions.cancel(str(proposal_id))
