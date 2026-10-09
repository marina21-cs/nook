import json
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.contracts import Candidate, Commit
from app.errors import AppError
from app.freshness import now
from app.item_repository import ItemRepository, encode


class CaptureService:
    def __init__(self, repository: ItemRepository) -> None:
        self.repo = repository
        self.store = repository.store

    def get_row(self, conn: sqlite3.Connection, draft_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            raise AppError(
                404,
                "capture_not_found",
                "Capture was discarded, saved or expired. Choose a photo again.",
            )
        age = (datetime.now(UTC) - datetime.fromisoformat(row["recorded_at"])).total_seconds()
        if age > self.repo.settings.draft_ttl_seconds:
            raise AppError(410, "capture_expired", "Capture expired. Choose a photo again.")
        return row

    @staticmethod
    def view(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "width": row["width"],
            "height": row["height"],
            "source": row["source"],
            "captured_at": row["captured_at"],
            "recorded_at": row["recorded_at"],
            "metadata_stripped": True,
            "photo_url": f"/api/captures/{row['id']}/photo",
            "candidates": json.loads(row["candidates"]),
            "saved_items": 0,
        }

    def get(self, draft_id: str) -> dict:
        with self.repo.db.lock, self.repo.db.connect() as conn:
            return self.view(self.get_row(conn, draft_id))

    def create(self, data: bytes, content_type: str, source: str) -> dict:
        with self.repo.db.lock:
            with self.repo.db.connect(write=True) as conn:
                expired = [
                    r["id"]
                    for r in conn.execute("SELECT id,recorded_at FROM drafts")
                    if (
                        datetime.now(UTC) - datetime.fromisoformat(r["recorded_at"])
                    ).total_seconds()
                    > self.repo.settings.draft_ttl_seconds
                ]
                for draft_id in expired:
                    conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
                    self.store.remove(draft_id, draft=True)
                if (
                    conn.execute("SELECT count(*) FROM drafts").fetchone()[0]
                    >= self.repo.settings.max_drafts
                ):
                    raise AppError(
                        409,
                        "draft_limit",
                        "At most 20 unsaved captures are allowed. Discard a draft first.",
                    )
                clean, width, height, digest = self.store.sanitize(data, content_type)
                self.store.check_quota(len(clean))
                draft_id, timestamp = str(uuid4()), now()
                captured_at = timestamp if source == "camera" else None
                self.store.write_private(self.store.path(draft_id, draft=True), clean)
                try:
                    conn.execute(
                        "INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?)",
                        (
                            draft_id,
                            digest,
                            width,
                            height,
                            source,
                            captured_at,
                            timestamp,
                            "[]",
                        ),
                    )
                    return self.view(self.get_row(conn, draft_id))
                except BaseException:
                    self.store.remove(draft_id, draft=True)
                    raise

    def discard(self, draft_id: str) -> dict:
        with self.repo.db.lock, self.repo.db.connect(write=True) as conn:
            conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
            self.store.remove(draft_id, draft=True)
            return {"discarded": True}

    def candidates(
        self, draft_id: str, candidates: list[Candidate], expected_generation: int
    ) -> dict:
        with self.repo.db.lock, self.repo.db.connect(write=True) as conn:
            self.get_row(conn, draft_id)
            if self.repo.db.generation(conn) != expected_generation:
                raise AppError(
                    409, "stale_request", "Collection changed while checking the photo. Retry."
                )
            conn.execute(
                "UPDATE drafts SET candidates=? WHERE id=?",
                (
                    encode([c.model_dump(mode="json") for c in candidates]),
                    draft_id,
                ),
            )
            return self.view(self.get_row(conn, draft_id))

    def commit(self, draft_id: str, request: Commit) -> dict:
        photo_id = str(uuid4())
        finalized = False

        def action(conn: sqlite3.Connection) -> dict:
            nonlocal finalized
            row = self.get_row(conn, draft_id)
            candidates = {c["id"]: c for c in json.loads(row["candidates"])}
            new_count = sum(r.identity == "new" for r in request.rows)
            if (
                conn.execute("SELECT count(*) FROM items").fetchone()[0] + new_count
                > self.repo.settings.max_items
            ):
                raise AppError(409, "item_limit", "Collection limit is 200 items.")
            # Validate the entire batch before any evidence finalization or item writes.
            for selection in request.rows:
                if selection.item_id:
                    self.repo.check_revision(
                        conn, str(selection.item_id), selection.expected_revision or 0
                    )
                if selection.candidate_id and str(selection.candidate_id) not in candidates:
                    raise AppError(
                        422, "candidate_not_found", "Candidate does not belong to this capture."
                    )
                if selection.region and (
                    selection.region.w * row["width"] < 1 or selection.region.h * row["height"] < 1
                ):
                    raise AppError(
                        422,
                        "region_too_small",
                        "Selected region must cover at least one evidence pixel.",
                    )
            self.store.finalize(draft_id, photo_id)
            finalized = True
            conn.execute(
                "INSERT INTO photos VALUES (?,?,?,?,?,?,?,1)",
                (
                    photo_id,
                    row["sha256"],
                    row["width"],
                    row["height"],
                    row["source"],
                    row["captured_at"],
                    row["recorded_at"],
                ),
            )
            ids = []
            for selection in request.rows:
                if selection.identity == "new":
                    item_id = self.repo.add_item(conn, selection)
                else:
                    item_id = str(selection.item_id)
                    for field in selection.model_fields_set & {
                        "personal_name",
                        "aliases",
                        "distinguishing_note",
                        "category",
                    }:
                        value = getattr(selection, field)
                        if field == "aliases":
                            value = encode(value)
                        # Field names are application-owned; omitted metadata is preserved.
                        conn.execute(f"UPDATE items SET {field}=? WHERE id=?", (value, item_id))
                candidate = (
                    candidates.get(str(selection.candidate_id)) if selection.candidate_id else None
                )
                self.repo.observation(
                    conn,
                    item_id,
                    request.location,
                    request.review_after_days,
                    photo_id=photo_id,
                    region=selection.region.model_dump() if selection.region else None,
                    candidate=candidate,
                    observed_at=row["captured_at"],
                    current=request.make_current,
                    bump=selection.identity == "existing",
                )
                ids.append(item_id)
            conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
            return self.repo.pointers(conn, ids)

        with self.repo.db.lock:
            try:
                result = self.repo.mutate(f"commit:{draft_id}", request, action)
            except BaseException:
                if finalized:
                    # If COMMIT outcome was uncertain, never remove a referenced complete asset.
                    with self.repo.db.connect() as conn:
                        exists = conn.execute(
                            "SELECT 1 FROM photos WHERE id=?", (photo_id,)
                        ).fetchone()
                    if not exists:
                        self.store.remove(photo_id)
                raise
            self.store.remove(draft_id, draft=True)
            return result
