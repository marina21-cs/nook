# Nook migration inventory

Migration must preserve household meaning, identifiers, timestamps and evidence while leaving the laptop store untouched until the user verifies the imported phone vault. This inventory comes from source/schema inspection; private live databases and photos were not opened.

## Source schema and data

The four ordered [SQL migrations](../../app/migrations) define schema versions 1–4. [Database.migrate](../../app/database.py) uses PRAGMA user_version and rejects a newer schema. Verify the actual exported version when migration is authorized; four scripts do not establish a private store's version.

| Source entity or location | Retain | Native treatment and validation |
| --- | --- | --- |
| items | UUID, revision, personal_name, aliases, distinguishing_note, category, created_at, updated_at, current_observation_id | Keep stable IDs; do not merge by name/category. Validate references and collision policy |
| observations | ID/item/photo links, region, candidate_provenance, location, location_state, confirmed_at, observed_at, provenance, review_after, evidence_status | Preserve history and unknowns; retain event time separately from record time; establish local sequence without inventing physical truth |
| photos | UUID, SHA256, normalized dimensions, source, captured_at, recorded_at, metadata_stripped | Export exact sanitized bytes, sizes and hashes; preserve shared associations and unavailable evidence |
| photos/ app-owned files | UUID JPEGs | Verify referenced assets; reject linked/outside paths; stage before activation |
| drafts table and drafts/ | Unconfirmed capture state | Proposed default: report and exclude from confirmed import. D13 decides explicit draft recovery; never silently promote |
| receipts | Idempotency key, operation, fingerprint, stored result | Keep audit/replay semantics. Scope legacy keys to their source vault; never execute them as new mobile operations. Decide import/expiry |
| meta generation/write_epoch | Invalidation and replay barrier | Preserve source provenance; deliberately initialize mobile vault/device namespace. Old queued writes cannot bypass the new boundary |
| poi_cache_meta / poi_cache_entries | Dataset label, import/source time, coverage, OSM namespace/ID/tags/coordinates, provenance | Separate public place cache from private vault; retain attribution; optional re-import only after D10 |
| Browser profile/preferences | Optional name/setup in localStorage | Explicit settings transfer if selected; not a confirmed household record |
| RAM proposals/chat/audio buffers | Ephemeral state | Exclude active execution/session tokens; invalidate proposals or reconstruct an unapproved preview |
| Models/runtime/wheels | Optional installation artifacts | Not vault memories; provision separately by compatible manifest after approval |
| .lock / ownership marker / temp DB files | Host protection/recovery markers | Do not transplant POSIX locks or half-written staging databases as a mobile vault |

Source implementation: [item repository](../../app/item_repository.py), [evidence store](../../app/evidence_store.py), [capture service](../../app/capture_service.py), [actions](../../app/actions.py), and [POI contracts](../../app/poi_contracts.py).

## Proposed versioned export contract

Implement a consistent read snapshot with export format/schema version, source application/build/schema identity, vault/source identifiers, export time, entity counts, original IDs/times/revisions, per-asset path/size/hash, unsupported-field report, and integrity metadata. Manifest paths must be bounded and relative. Source-code archives from [build_v1_archive.py](../../scripts/build_v1_archive.py) are not personal-data exports or encrypted backups.

Use a consistent SQLite snapshot and matching media inventory; do not copy a live DB mid-write. Preserve timestamps exactly. Missing media remains a surfaced missing-asset result; never substitute an unrelated image or silently report completeness.

Dry-run checks supported version, path traversal, absolute paths, symlinks, duplicate entries, archive/decompression limits, foreign keys, ID collisions, storage needs, field semantics, and asset hashes. Refuse unsupported fields or return an explicit unresolved report; never silently discard them.

## Activation and interruption

1. Export into a new private location; verify the source stays unchanged.
2. Validate without mutation and show counts/assets/collisions.
3. Stage a separate target DB and media tree with an activation journal.
4. Verify every entity/reference, count, hash and domain invariant.
5. Activate only a complete verified target through a recoverable switch.
6. Open it, recall old/unknown/backdated records, and obtain user verification before considering source retirement.

Before activation, interruption leaves the old vault usable. During activation, the journal must recover the old complete state or new complete state. SQLite rollback alone cannot undo media copies. Preserve source and last-good target; rollback must not erase post-import user writes.

## Required rehearsal

[02-L09](02-native-local-alpha/TEST_PLAN.md) covers every declared export version, interrupted import, missing/corrupt assets, shared photos, ID collisions, unsupported fields, adversarial archives, storage exhaustion and activation recovery. [01-F10](01-feasibility/TEST_PLAN.md) establishes a small synthetic mapping first. [04-B06](04-backup-recovery/TEST_PLAN.md) extends activation recovery to restore. [05-S08](05-device-sync/TEST_PLAN.md) checks schema/deletion continuity under sync.

Expected evidence: version matrix, source/target counts, ID/time comparison, media hashes, dry-run report, journal fault results, user-verification receipt and untouched-source proof. Status: not run.
