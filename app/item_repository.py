import hashlib
import json
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.contracts import (
    AddObservation,
    DeleteData,
    DeleteItem,
    Edit,
    ManualCreate,
    NamedFields,
)
from app.database import Database
from app.errors import AppError
from app.evidence_store import EvidenceStore
from app.freshness import freshness, now


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ItemRepository:
    RECEIPT_LIMIT = 10000

    def __init__(self, settings: Settings, store: EvidenceStore) -> None:
        self.settings = settings
        self.store = store
        self.db = Database(store.root / "items.sqlite")
        self.db.migrate()
        self.recover()

    def recover(self) -> None:
        with self.db.lock, self.db.connect(write=True) as conn:
            conn.execute("DELETE FROM drafts")
            conn.execute(
                "DELETE FROM photos WHERE id NOT IN (SELECT photo_id FROM observations WHERE photo_id IS NOT NULL)"
            )
            referenced = {r[0] for r in conn.execute("SELECT id FROM photos")}
        self.store.cleanup(referenced)
        # A crash before an atomic delete-all replacement leaves only this app-owned staging DB.
        for suffix in ("", "-journal"):
            (self.store.root / ("items.next.sqlite" + suffix)).unlink(missing_ok=True)

    def generation(self) -> int:
        with self.db.lock, self.db.connect() as conn:
            return self.db.generation(conn)

    def check_revision(self, conn: sqlite3.Connection, item_id: str, revision: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise AppError(404, "item_not_found", "Item no longer exists.")
        if row["revision"] != revision:
            raise AppError(
                409,
                "revision_conflict",
                "Reload the item before editing.",
                current_revision=row["revision"],
            )
        return row

    def photo_view(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            **dict(row),
            "metadata_stripped": bool(row["metadata_stripped"]),
            "available": self.store.available(row["id"]),
            "url": f"/api/photos/{row['id']}",
        }

    def item_view(self, conn: sqlite3.Connection, item_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise AppError(404, "item_not_found", "Item no longer exists.")
        result = dict(row)
        result["aliases"] = json.loads(result["aliases"])
        observations = []
        current = None
        for observation in conn.execute(
            "SELECT * FROM observations WHERE item_id=? ORDER BY confirmed_at DESC, rowid DESC",
            (item_id,),
        ):
            value = dict(observation)
            photo = None
            if value["photo_id"]:
                asset = conn.execute(
                    "SELECT * FROM photos WHERE id=?", (value["photo_id"],)
                ).fetchone()
                if asset:
                    photo = self.photo_view(asset)
            value["photo"] = photo
            if photo and not photo["available"]:
                value["evidence_status"] = "unavailable"
            for field in ("region", "candidate_provenance"):
                value[field] = json.loads(value[field]) if value[field] else None
            value.pop("photo_id")
            value.pop("item_id")
            observations.append(value)
            if value["id"] == result["current_observation_id"]:
                current = value
        result.pop("current_observation_id")
        result["observations"] = observations
        result["current_observation"] = current
        result["location"] = current["location"] if current else None
        result["location_label"] = "Last recorded" if result["location"] else "Location unknown"
        result["freshness"] = freshness(
            current, current["photo"] if current else None, result["created_at"]
        )
        result["live_location_verified"] = False
        return result

    def get(self, item_id: str) -> dict[str, Any]:
        with self.db.lock, self.db.connect() as conn:
            return self.item_view(conn, item_id)

    def all(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        return [
            self.item_view(conn, r[0])
            for r in conn.execute("SELECT id FROM items ORDER BY updated_at DESC, id")
        ]

    def materialize(self, conn: sqlite3.Connection, result: dict, replayed: bool) -> dict:
        value = dict(result)
        if "items" in result:
            for item in result["items"]:
                try:
                    self.check_revision(conn, item["id"], item["revision"])
                except AppError as exc:
                    raise AppError(
                        409,
                        "stale_receipt",
                        "This operation was already saved and its records later changed. Reload the collection.",
                    ) from exc
            value["items"] = [self.item_view(conn, r["id"]) for r in result["items"]]
        return {
            **value,
            "generation": self.db.generation(conn),
            "write_epoch": self.write_epoch(conn),
            "replayed": replayed,
        }

    @staticmethod
    def write_epoch(conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT value FROM meta WHERE key='write_epoch'").fetchone()[0])

    def retain_receipts(self, conn: sqlite3.Connection, newest_key: str) -> None:
        if conn.execute("SELECT count(*) FROM receipts").fetchone()[0] > self.RECEIPT_LIMIT:
            # Rotate before forgetting any key. Old absent requests cannot execute again.
            conn.execute("UPDATE meta SET value=value+1 WHERE key='write_epoch'")
            conn.execute("DELETE FROM receipts WHERE key<>?", (newest_key,))

    @staticmethod
    def request_payload(request: Any) -> dict:
        payload = request.model_dump(mode="json")
        if payload.get("write_epoch") == 0:
            payload.pop("write_epoch")  # Preserve pre-migration receipt fingerprints.
        if hasattr(request, "rows") and any(r.identity == "existing" for r in request.rows):
            # Omission and explicit clearing have different update semantics.
            payload["_existing_row_fields"] = [
                sorted(r.model_fields_set) if r.identity == "existing" else None
                for r in request.rows
            ]
        return payload

    @staticmethod
    def fingerprint(operation: str, payload: Any) -> str:
        return hashlib.sha256(encode([operation, payload]).encode()).hexdigest()

    def receipt(
        self,
        conn: sqlite3.Connection,
        operation: str,
        key: str,
        fingerprint: str,
        write_epoch: int = 0,
    ) -> dict | None:
        row = conn.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
        if row:
            if row["operation"] == "invalidated":
                raise AppError(
                    409,
                    "stale_receipt",
                    "This operation predates a deletion. Review the collection before a new write.",
                )
            if row["operation"] != operation or row["fingerprint"] != fingerprint:
                raise AppError(
                    409, "idempotency_conflict", "Idempotency key was used for another payload."
                )
            return self.materialize(conn, json.loads(row["result"]), True)
        if not (
            operation.startswith("delete:") or operation == "delete_all"
        ) and write_epoch != self.write_epoch(conn):
            raise AppError(
                409,
                "stale_receipt",
                "Write epoch expired. Review current data and explicitly confirm a new operation with a fresh key and epoch.",
                current_write_epoch=self.write_epoch(conn),
            )
        return None

    def mutate(
        self, operation: str, request: Any, action: Callable[[sqlite3.Connection], dict]
    ) -> dict:
        fingerprint = self.fingerprint(operation, self.request_payload(request))
        with self.db.lock, self.db.connect(write=True) as conn:
            previous = self.receipt(
                conn, operation, str(request.idempotency_key), fingerprint, request.write_epoch
            )
            if previous is not None:
                return previous
            result = action(conn)
            self.db.changed(conn)
            conn.execute(
                "INSERT INTO receipts VALUES (?,?,?,?)",
                (
                    str(request.idempotency_key),
                    operation,
                    fingerprint,
                    encode(result),
                ),
            )
            self.retain_receipts(conn, str(request.idempotency_key))
            return self.materialize(conn, result, False)

    def add_item(self, conn: sqlite3.Connection, named: NamedFields) -> str:
        if conn.execute("SELECT count(*) FROM items").fetchone()[0] >= self.settings.max_items:
            raise AppError(
                409,
                "item_limit",
                "Collection limit is 200 items. Remove a record before adding one.",
            )
        item_id, timestamp = str(uuid4()), now()
        conn.execute(
            "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,NULL)",
            (
                item_id,
                1,
                named.personal_name,
                encode(named.aliases),
                named.distinguishing_note,
                named.category,
                timestamp,
                timestamp,
            ),
        )
        return item_id

    def observation(
        self,
        conn: sqlite3.Connection,
        item_id: str,
        location: str | None,
        review_days: int | None,
        photo_id: str | None = None,
        region: Any = None,
        candidate: Any = None,
        observed_at: str | None = None,
        current: bool = True,
        bump: bool = True,
    ) -> None:
        if (
            conn.execute(
                "SELECT count(*) FROM observations WHERE item_id=?", (item_id,)
            ).fetchone()[0]
            >= 100
        ):
            raise AppError(
                409,
                "observation_limit",
                "Item history limit is 100 observations. Review/delete the record before adding more.",
            )
        observation_id, timestamp = str(uuid4()), now()
        review = (
            (datetime.now(UTC) + timedelta(days=review_days)).isoformat() if review_days else None
        )
        conn.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                observation_id,
                item_id,
                photo_id,
                encode(region) if region else None,
                encode(candidate) if candidate else None,
                location,
                "recorded" if location else "unknown",
                timestamp,
                observed_at,
                "photo_confirmed" if photo_id else "user_report",
                review,
                "available" if photo_id else "no_new_photo",
            ),
        )
        if current:
            conn.execute(
                "UPDATE items SET current_observation_id=? WHERE id=?", (observation_id, item_id)
            )
        conn.execute(
            "UPDATE items SET revision=revision+?, updated_at=? WHERE id=?",
            (int(bump), timestamp, item_id),
        )

    @staticmethod
    def pointers(conn: sqlite3.Connection, ids: list[str]) -> dict:
        return {
            "items": [
                {
                    "id": item_id,
                    "revision": conn.execute(
                        "SELECT revision FROM items WHERE id=?", (item_id,)
                    ).fetchone()[0],
                }
                for item_id in ids
            ]
        }

    def create_manual(self, request: ManualCreate) -> dict:
        def action(conn: sqlite3.Connection) -> dict:
            item_id = self.add_item(conn, request)
            self.observation(conn, item_id, request.location, request.review_after_days, bump=False)
            return self.pointers(conn, [item_id])

        return self.mutate("manual_create", request, action)

    def edit(self, item_id: str, request: Edit) -> dict:
        def action(conn: sqlite3.Connection) -> dict:
            self.check_revision(conn, item_id, request.expected_revision)
            for field in request.model_fields_set & {
                "personal_name",
                "aliases",
                "distinguishing_note",
                "category",
            }:
                value = getattr(request, field)
                if field == "aliases":
                    value = encode(value)
                # field is a code-owned allowlist, never model/user SQL.
                conn.execute(f"UPDATE items SET {field}=? WHERE id=?", (value, item_id))
            conn.execute(
                "UPDATE items SET revision=revision+1,updated_at=? WHERE id=?", (now(), item_id)
            )
            return self.pointers(conn, [item_id])

        return self.mutate(f"edit:{item_id}", request, action)

    def add_observation(self, item_id: str, request: AddObservation) -> dict:
        def action(conn: sqlite3.Connection) -> dict:
            self.check_revision(conn, item_id, request.expected_revision)
            self.observation(conn, item_id, request.location, request.review_after_days)
            return self.pointers(conn, [item_id])

        return self.mutate(f"observe:{item_id}", request, action)

    def cleanup_photos(self) -> None:
        with self.db.lock, self.db.connect(write=True) as conn:
            conn.execute(
                "DELETE FROM photos WHERE id NOT IN (SELECT photo_id FROM observations WHERE photo_id IS NOT NULL)"
            )
            referenced = {r[0] for r in conn.execute("SELECT id FROM photos")}
            for path in self.store.photos.iterdir():
                if path.suffix in (".jpg", ".part"):
                    try:
                        from uuid import UUID

                        str(UUID(path.stem))
                    except ValueError:
                        continue
                    if path.suffix == ".part" or path.stem not in referenced:
                        path.unlink(missing_ok=True)
            self.store.sync_dir(self.store.photos)

    def deletion_preview(self, item_id: str) -> dict:
        with self.db.lock, self.db.connect() as conn:
            item = self.item_view(conn, item_id)
            photos = {o["photo"]["id"] for o in item["observations"] if o["photo"]}
            affected: set[str] = set()
            for photo_id in photos:
                affected.update(
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT item_id FROM observations WHERE photo_id=? AND item_id<>?",
                        (photo_id, item_id),
                    )
                )
            return {
                "item_id": item_id,
                "revision": item["revision"],
                "personal_name": item["personal_name"],
                "photo_count": len(photos),
                "shared_with_item_ids": sorted(affected),
                "warning": "Shared photos may retain this item's pixels. Choose all_affected to remove those photos from every record."
                if affected
                else None,
            }

    def delete(self, item_id: str, request: DeleteItem) -> dict:
        def action(conn: sqlite3.Connection) -> dict:
            self.check_revision(conn, item_id, request.expected_revision)
            photos = {
                r[0]
                for r in conn.execute(
                    "SELECT photo_id FROM observations WHERE item_id=? AND photo_id IS NOT NULL",
                    (item_id,),
                )
            }
            affected: set[str] = set()
            retained = False
            for photo_id in photos:
                shared = {
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT item_id FROM observations WHERE photo_id=? AND item_id<>?",
                        (photo_id, item_id),
                    )
                }
                if shared and request.evidence_scope == "unreferenced":
                    retained = True
                if request.evidence_scope == "all_affected":
                    affected.update(shared)
                    conn.execute(
                        "UPDATE observations SET photo_id=NULL,region=NULL,candidate_provenance=NULL,evidence_status='removed' WHERE photo_id=?",
                        (photo_id,),
                    )
                    conn.execute("DELETE FROM photos WHERE id=?", (photo_id,))
            for affected_id in affected:
                conn.execute(
                    "UPDATE items SET revision=revision+1,updated_at=? WHERE id=?",
                    (now(), affected_id),
                )
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            # Keep only keys/hashes for invalidated writes: a late retry must not recreate data.
            conn.execute(
                "UPDATE receipts SET operation='invalidated',result='{}' WHERE operation NOT LIKE 'delete:%' AND operation<>'delete_all'"
            )
            # Drafts may include deleted pixels or a pending existing-item identity. Discard conservatively.
            conn.execute("DELETE FROM drafts")
            return {
                "deleted": True,
                "shared_pixels_retained": retained,
                "affected_item_count": len(affected),
                "evidence_scope": request.evidence_scope,
                "erasure": "application deletion; exports and OS backups are outside this app",
            }

        with self.db.lock:
            result = self.mutate(f"delete:{item_id}", request, action)
            self.cleanup_photos()
            with self.db.connect() as conn:
                referenced_drafts = {r[0] for r in conn.execute("SELECT id FROM drafts")}
            for path in self.store.drafts.iterdir():
                if path.suffix in (".jpg", ".part"):
                    try:
                        from uuid import UUID

                        str(UUID(path.stem))
                    except ValueError:
                        continue
                    if path.suffix == ".part" or path.stem not in referenced_drafts:
                        path.unlink(missing_ok=True)
            self.store.sync_dir(self.store.drafts)
            self.db.compact()
        return result

    def delete_all(self, request: DeleteData) -> dict:
        operation = "delete_all"
        fingerprint = self.fingerprint(operation, self.request_payload(request))
        with self.db.lock:
            with self.db.connect() as conn:
                previous = self.receipt(conn, operation, str(request.idempotency_key), fingerprint)
                if previous:
                    self.cleanup_photos()
                    return previous
                generation = self.db.generation(conn)
                epoch = self.write_epoch(conn)
                if generation != request.expected_generation:
                    raise AppError(
                        409,
                        "generation_conflict",
                        "Collection changed. Review it before deleting all data.",
                        current_generation=generation,
                    )
                if self.db.on_changed is not None:
                    self.db.on_changed()
                count = conn.execute("SELECT count(*) FROM items").fetchone()[0]
                # The epoch rejects all earlier unretained writes without copying tombstones.
            # Build a fresh empty schema, fsync and atomically replace the old database.
            replacement = Database(self.store.root / "items.next.sqlite")
            for suffix in ("", "-journal"):
                (self.store.root / ("items.next.sqlite" + suffix)).unlink(missing_ok=True)
            replacement.migrate()
            result = {
                "deleted": True,
                "item_count": count,
                "model_files_retained": True,
                "erasure": "application deletion; exports, SSD snapshots and OS backups are outside this app",
            }
            with replacement.connect(write=True) as conn:
                conn.execute("UPDATE meta SET value=? WHERE key='generation'", (generation + 1,))
                conn.execute("UPDATE meta SET value=? WHERE key='write_epoch'", (epoch + 1,))
                conn.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?)",
                    (str(request.idempotency_key), operation, fingerprint, encode(result)),
                )
            fd = os.open(replacement.path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(replacement.path, self.db.path)
            self.store.sync_dir(self.store.root)
            self.store.cleanup(set())
            for suffix in ("-journal", "-wal", "-shm"):
                self.db.path.with_name(self.db.path.name + suffix).unlink(missing_ok=True)
            return {
                **result,
                "generation": generation + 1,
                "write_epoch": epoch + 1,
                "replayed": False,
            }
