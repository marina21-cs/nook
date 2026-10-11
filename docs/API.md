## Opt-in contextual local chat — 10 October 2026

This section supersedes the earlier deterministic-only chat description below. `APP_CHAT_ENABLED=1` enables the pinned local Ollama provider; the default remains disabled. Set a dedicated loopback `APP_CHAT_PORT` (11435 in accepted smoke), not the default11434 or the app port. `APP_CHAT_TIMEOUT` must be finite, greater than0 and at most30 seconds; accepted smoke used25 seconds. Runtime/model provisioning is a separate explicit operator action; API requests never install, download or start services.

`POST /api/chat` accepts strict `{query, request_id, context_id?}` with session/CSRF protection. When enabled, `kind` may be `generated`; responses include `context_id`, `context_expires_in_seconds`, `reply_authority`, `general_conversation_available`, `inference_used` and `persisted`. A generated answer has `inference_used:true`, `reply_authority:"generated_unverified"`, `persisted:false` and `recall:null`. The visible text is labeled generated and unverified. Saved-item results use `reply_authority:"saved_records"` and `inference_used:false`; saved names/aliases and personal lookups retain deterministic provenance, uncertainty and last-recorded semantics. Narrow saved-item pronouns reread the authoritative record rather than trusting generated history. Unknown personal items remain unknown.

Send the returned context ID for a follow-up. The context belongs to the server session, expires five minutes after creation and retains at most three complete conversation pairs in RAM, with bounded history/prompt bytes. It is not a saved transcript. `DELETE /api/chat` takes `{request_id, context_id}` and invalidates that session-owned context. Reset, expiry, restart, writes/deletes and cancelled/error turns can invalidate it; a stale or foreign ID returns409 `chat_context_unavailable`. Clients should clear their ID and start a new conversation. Only one active turn per context and one active provider call are allowed; busy requests fail visibly.

The runtime must expose the exact pinned model name/manifest digest from `app/config.py`. Model-list validation and generation share one whole-call deadline. Responses are bounded and strictly parsed; unexpected tools, reasoning fields, truncation, malformed JSON and oversize replies fail closed. Relevant errors include503 `chat_disabled`, `chat_unavailable`, `chat_model_unverified`, `chat_timeout`, `chat_invalid_output` and `chat_busy`; context/validation errors use409/422. No generated answer can authorize a record write, execute a command or send an external message. Explicit action preview/approval remains a separate API.

When enabled, typed browser chat has a35-second complete-response deadline; deterministic disabled-mode chat and action previews keep10 seconds. Cancellation discards late output and clears context. Retry uses a new request ID after errors; uncertain writes continue to preserve their own idempotency keys. Status reports configuration without runtime probing and is not an acceptance certificate.

Actual HTTP smoke passed on one Linux laptop using Ollama0.30.6 and Qwen2.5 0.5B Instruct Q4_K_M: two generated responses took5.452s and4.370s, with same context ID; known/unknown grounded recall, reset, restart and unavailable-runtime behavior passed. The follow-up repeated the initial sentence while retaining requested facts; broad quality is not established. Real generated UI capture remains pending. Speech routes remain a separate grounded voice pipeline and do not synthesize these generated replies. Evidence: `docs/candidates/local-chat-20261010/FINAL_ACCEPTANCE.json` and `evidence/realchat20261010e/result.json`.

---

## Bounded typed chat repair — 2026-10-09

`POST /api/chat` takes strict `{query, request_id}` with the same session, CSRF, UUID and query validation as recall. It returns `kind` (`greeting`, `help`, `memory`, `unknown`, `clarify`, `unsupported`), `request_id`, `generation`, optional `recall`, and optional `reply_text`. `general_conversation_available`, `inference_used` and `persisted` are always false. This is deterministic guidance and saved-item lookup, not general multi-turn AI. It never writes records or calls a model. Existing action proposals retain their separate confirmation path.

Exact supported greetings/help receive visible guidance; unmatched general questions explain the current capability. Saved names/aliases use the existing deterministic last-recorded lookup with ambiguity, provenance and unknown-location handling. Requests participate in the existing cancellation and request-ID replay registry. No chat transcript is stored.

The typed browser uses a 10-second complete-response deadline for chat and action preview. Other API calls have a 35-second complete-response deadline. Session refresh/retry shares the original deadline. Empty/whitespace Send displays guidance; network failure and timeout expose retryable visible states. Cancellation prevents delayed output from repainting. Uncertain writes preserve the original payload/idempotency key for retry. These are client deadlines, not model performance claims.

Runtime verification status is tracked in `deliverables/nook-chat-repair/REPORT.md`; do not apply prior 408/31 results to these changes.

## Voice qualification update

Voice remains unprovisioned: no complete weight manifest or actual STT/TTS acceptance. `speech.spoken_text` exposes the exact brief narration when audio renders; full timestamps remain in the structured record and text response. The one-test `APP_VOICE_TEST_GUARD_54=1` policy is explicitly authorized for the supervised smoke only; default remains 52°C and no sensor/OS setting changes. The smoke has not started because the retained swap guard stopped provisioning. See `../VOICE_IMPLEMENTATION_REPORT.md`.

---

## Schema v3 update — receipt retention and metadata semantics

All explicitly confirmed personal-memory write bodies accept `write_epoch` (integer ≥0; omission means 0). `/api/status` and successful mutation responses expose the current epoch. After receipt rollover or reset, clients must review current data and explicitly confirm a new operation using a fresh idempotency key and current epoch. Do not silently update an old queued payload. Expired absent requests fail with 409 `stale_receipt` and `details.current_write_epoch`.

The receipt cap no longer blocks deletion. At over 10,000 receipts, an atomic epoch rotation retains the newest receipt; older absent writes cannot run with their expired epoch. Whole reset advances generation/epoch and retains only its receipt. Revision-checked item deletion and generation-checked reset remain possible independently of expired epochs. Retained retries remain non-mutating; pruned old reset requests fail their generation check. This supersedes the older tombstone-retention and hard-cap description below.

Existing-item photo commits preserve omitted aliases, note and category. Explicit `[]`, `""`, and `null` clear those fields respectively. Field presence participates in idempotency for existing rows; old existing-photo receipt retries may conflict following this semantic change. New rows retain defaults.

MPO/multi-frame input remains deliberately rejected. No target-phone incompatibility is asserted. Overdue review dates take precedence over unknown imported-photo time, while provenance still reports the unknown timestamp. Async database waits no longer intentionally hold the event loop.

`POST /api/speech/transcribe` accepts `{request_id, audio:{content_type:"audio/wav",data_base64},language_hint:"en"|"tl"|"auto"}`. WAV must be canonical mono 16 kHz PCM16, audible and at most 10 seconds; JSON is capped at 512 KiB. It returns an editable, unconfirmed transcript with no lookup or persistence. `POST /api/speech/turns` accepts a fresh `request_id`, edited `utterance`, and literal `transcript_confirmed:true`; it performs deterministic read-only recall and requests English speech. It cannot save/delete or execute model-selected tools. Existing `/api/requests/{id}/cancel` handles both steps. Provider disabled/missing returns typed guidance; TTS failures preserve the grounded text.

Local speech is opt-in via `APP_VOICE_ENABLED=1`; artifacts and dependencies are not yet provisioned. Enabling the flag does not install/download anything or establish inference acceptance. `/api/status.speech` exposes contract/provisioning state and `real_inference_accepted:false`. The fixed CPU worker and API routes passed focused fake-provider tests only; full post-integration and real guarded speech verification are pending. Output WAV is mono PCM16 at 24 kHz, at most 30 seconds/1,440,044 bytes; this supersedes the earlier 256 KiB output bound.

---

# Backend API contract

Base: `http://127.0.0.1:8765`; use one origin consistently. Exact Host/Origin checks reject other ports/hosts, `Origin: null` and cross-site requests. No CORS or LAN serving is configured. Forwarded headers never expand the boundary.

`GET /api/session` returns `{csrf_token, expires_in_seconds:3600}` and an HttpOnly, SameSite=Strict cookie. Use the cookie for reads and `X-CSRF-Token` for every non-GET operation. This is ephemeral localhost session/CSRF protection for one OS user, not multi-user authentication or phone pairing. `GET /api/status` requires no session and returns actual configured/installed model status, storage readiness, counts and limits; it makes no internet probe.

| Endpoint | Contract |
| --- | --- |
| `GET /api/status` | Runtime/model readiness, schema/generation, limits; text-only models never reported as vision |
| `GET /api/session` | New ephemeral cookie/CSRF token; restart invalidates sessions |
| `POST /api/captures?source=import\|camera` | Raw JPEG/PNG/still-WebP bytes → 201 draft; import default, zero saved items |
| `GET /api/captures/{id}` | Draft metadata/candidates; 404 after commit/discard/restart, 410 after expiry |
| `GET /api/captures/{id}/photo` | Sanitized draft JPEG, no-store, session required |
| `POST /api/captures/{id}/suggest` | `{request_id:UUID}` → unconfirmed candidates with category/score/box/model digest; 503 when unavailable, draft preserved |
| `POST /api/captures/{id}/commit` | Explicit confirmed rows + location + idempotency key → records/photo committed; no automatic identity merge |
| `DELETE /api/captures/{id}` | Discard temporary bytes and any pending photo check; repeated discard succeeds |
| `GET /api/items?query=…&offset=0&limit=20` | Confirmed collection only, total and generation; limit 1–50; supports browsing all clarification matches |
| `POST /api/items` | Confirmed personal name, aliases/note/category, `location:string\|null`, UUID idempotency key; manual user-report provenance, no photo |
| `GET /api/items/{id}` | Current revision, observation/history, evidence status, stored location and freshness |
| `PATCH /api/items/{id}` | Confirmation/key/expected revision plus reviewed name/aliases/note/category; metadata edits do not refresh observation time |
| `POST /api/items/{id}/observations` | Confirmation/key/expected revision + `location:string\|null`, optional review-after days; new user-report observation, no new photo |
| `GET /api/items/{id}/deletion-preview` | Name/revision/photo count and surviving item IDs sharing evidence; explains retained pixels |
| `DELETE /api/items/{id}` | Confirmation/key/expected revision and explicit evidence scope; deletion receipt, no cached saved names |
| `DELETE /api/data` | Confirmation/key, exact `confirmation:"DELETE ALL LOCAL DATA"`, expected generation; fresh empty DB, app photo/draft cleanup, model files retained |
| `POST /api/recall` | `{query,request_id,use_inference:false}` → found/clarify/unknown, exact stored records, revisions/photos, inference/fallback flags |
| `POST /api/requests/{id}/cancel` | Cancel/discard an active result; also covers Stop arriving before the request; IDs are single-use in a bounded in-memory window |
| `GET /api/photos/{id}` | Referenced local evidence JPEG; 404 if unavailable/deleted; never substitutes another photo |
| `GET /openapi.json` | Authenticated local schema; no external documentation assets |

Vision defaults to the provisioned, hash-pinned NanoDet model through OpenCV DNN on CPU. Status distinguishes configured availability from `inference_verified` in this server process. `/suggest` returns `{request_id,candidates,inference_used:true,elapsed_ms,draft_saved_items:0,identity_verified:false,location_verified:false,inventory_complete:false,manual_confirmation_required:true}`. Empty candidates are a successful image check, never an empty-inventory assertion. Each candidate contains UUID, finite category/score, normalized region and exact model identity/digest. The supported 80 categories and unsupported examples are reported by status. Maximum 20 candidates, fixed score threshold 0.35 and class-aware NMS IoU 0.6. One isolated worker per request, two CPU threads, no GPU/OpenCL, no automatic download or text-model vision substitution. Wrong/missing/changed weights, incompatible runtime, worker error/timeout preserve the draft and manual workflow. [Measured results and limitations](VISION_RESULTS.md).

## Confirmation payloads

All object schemas forbid unknown fields. Names/aliases: 1–80 characters, at most 10 distinct aliases. Note/location: at most 240. Query: 1–2000. Confirmation must be the literal boolean `true`, not 1 or a string. IDs and keys are UUIDs. JSON duplicate keys and non-finite numbers are rejected before schema parsing. Server timestamps and asset paths are never accepted from model/API data.

```json
{
  "confirmed": true,
  "idempotency_key": "49d2dd79-2eeb-40e0-b553-ec79b5d03f34",
  "location": "Hall cabinet → top drawer",
  "make_current": true,
  "review_after_days": 7,
  "rows": [
    {
      "identity": "new",
      "personal_name": "blue craft scissors",
      "aliases": ["blue shears"],
      "distinguishing_note": "blue handle",
      "category": "scissors",
      "region": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
    }
  ]
}
```

Regions use the oriented, resized evidence image: x/y/w/h in 0–1, positive dimensions, within the image, at least one pixel. Null region confirms the item using the full photo context. `candidate_id` is optional and must belong to this draft; its original inferred category/score/region/model remain separately stored as `candidate_provenance`. The reviewed category/region/name/location never overwrite that provenance.

To update an existing identity, use `identity:"existing"`, `item_id` and `expected_revision` in that row. New identities forbid those fields. A batch cannot update the same ID twice. Similar names/categories produce separate records until the user chooses an existing ID. GET item search supports reviewing possible duplicates; image-similarity matching is not implemented.

`make_current` defaults to false: a historical observation is saved without resetting the current observation. A new historical-only item has unknown current location. `source=import` records no capture timestamp; EXIF time and GPS are removed. `source=camera` is the caller's deliberate capture assertion and uses receipt time as the capture estimate. Seven-day freshness is an optional preference, not a validated expiry or live-location claim.

Moves with a new photo use a new capture/commit and the existing identity. Without a photo, POST an observation; the result says `user_report` and `no_new_photo`. Old dated photos remain in history, never as the current move's evidence. Setting location null marks moved/unknown and cannot resurrect an older location. PATCH only edits metadata; location changes require an observation.

## Recall and frontend rules

Recall retains the original query's distinguishing words and searches only approved names, aliases, note and category. Detector candidates and their raw labels are excluded. All plausible matches are counted before the five-card display cap. More than one match returns clarify; no match or a single item with unknown location returns unknown. Negation/action/instruction queries are conservatively unsupported. Ranking is ordering, not probability. This is bounded English-style label/alias search; arbitrary multilingual semantic recall is unverified.

Cards say `Last recorded`, with `live_location_verified:false`, even for a recent photo. `freshness` is `last_recorded`, `needs_recheck`, `unknown_clock`, `unknown_photo_time`, or `unknown_location`. Current observation owns its location/date/photo; the item history is explicitly historical. Missing photos retain recorded metadata with evidence unavailable.

Keep `id`, `revision`, `generation` and `request_id` in frontend state. Metadata mutations invalidate pending searches by generation; delete/discard also cancels pending inference. Late results return 409 without old records. Previously delivered cards cannot be recalled from the browser: discard them after a mutation and reload. Render saved/image text as text, never HTML. Do not describe candidates as identity, inventory completeness, a detected move, present location or medical/hazard advice.

## Retry, storage and deletion

Idempotency applies to commit, manual create, metadata edits, observations, item deletion and delete-all. Reuse the exact key/body/path on network/storage retry. Another payload with the same key returns 409. A receipt whose referenced item later changed returns `stale_receipt`, not an old snapshot. Item deletion invalidates earlier non-deletion write receipts. Only their UUID retry keys and SHA256 fingerprints remain; item IDs and receipt results are cleared. Those retries return 409 `stale_receipt` and cannot recreate deleted records or duplicate surviving records. Review the current collection and use a new key for an intentional new write. Delete-all carries all previous keys/fingerprints into the fresh database as invalidated receipts, including older deletion keys. A retry of the most recent delete-all returns its receipt and never removes later records or drafts; a deletion invalidated by a subsequent delete-all returns 409.

Photos are decoded/re-encoded, fsynced and atomically finalized before the referencing SQLite transaction commits. Failures preserve the draft where safe. Startup removes orphan assets/partial files and all abandoned drafts. Referenced missing evidence is reported unavailable. SQLite migrations are transactional and reject a future schema version. A process lock prevents multiple workers opening the same data directory.

Limits: 10 MiB upload; 24 million decoded pixels; 2048-pixel maximum evidence edge; 64 KiB JSON body; 15-second body/inference budgets; four simultaneous uploads/active inference requests; 20 drafts; five selected rows; 200 items; 100 observations per item; 512 MiB evidence quota including staging; 10,000 bounded write receipts. Expired drafts are cleaned on the next upload, and all drafts are discarded on restart. These initial limits require real-photo usability review.

Deletion scope `unreferenced` removes only photos no surviving item references. A shared photo can retain deleted-item pixels; the preview/receipt says so. `all_affected` removes those photo files/references from all affected observations, clears derived regions/candidate provenance and bumps surviving revisions; their confirmed location remains with `evidence_status:"removed"`. A new item deletion conservatively discards pending drafts. Replaying a completed deletion preserves newer drafts and pending work. Metadata and file cleanup run under the same storage lock; cleanup removes only drafts no longer referenced by the database. A short frontend confirmation should name the item and show the preview before sending the delete request.

Delete-all atomically replaces the old DB with a fresh empty schema containing generation, the current deletion receipt and minimal invalidated retry keys/fingerprints (no item IDs, names, locations, photos or old result bodies), then cleans app assets. The directory marker and process lock remain. It never removes model files, unknown/unrelated files, exports, OS backups or SSD/snapshot bytes. This is application deletion, not forensic erasure. There is no import/export endpoint or hidden conversation archive.

## Errors

```json
{"error":{"code":"revision_conflict","message":"Reload the item before editing.","details":{"current_revision":2}}}
```

400 malformed framing/header; 401 expired/missing session; 403 host/origin/CSRF; 408 body timeout; 409 revision/generation/idempotency/limits/cancelled/stale result; 410 draft expired; 413 byte/pixel limits; 415 unsupported image/JSON media type; 422 invalid image/schema/JSON; 503 unavailable/busy inference/storage; 504 vision timeout. Validation details identify fields without echoing photo/text input. Errors omit storage paths, prompts and stack traces. No model output can issue file reads, shell commands, SQL, HTTP destinations or record mutations.


## Bounded turns (implemented backend contract)

`POST /api/turns` accepts `{request_id:UUID,utterance:string,intent:"recall"|"category"|"visual_question",language:"en"|"fil"|"auto",frame?:{content_type,data_base64},use_vision:false,use_recall_inference:false,render_speech:false}`. Utterance is one editable typed transcript, 1–2000 characters. Optional frame is one JPEG/PNG/still WebP, at most 256 KiB decoded (base64 limit 349528 characters), sanitized/oriented in memory; existing pixel/edge checks apply. Turn JSON is at most 352 KiB; up to four concurrent bodies and four active requests, IDs share the existing single-use cancel registry. This smaller frame limit is a conservative backend contract, not tested mobile UX.

Turn response includes kind (`memory`, `clarify`, `unknown`, `candidate`, `unsupported`), application-owned `reply_text`, exact nested `/recall` result where relevant, tentative candidates, inference/speech status, generation, frame metadata and `persisted:false`. Turn input is never logged or saved as item/observation/draft/photo. Recall reads existing saved evidence; those nested photos are previously confirmed memory, not a save of the current frame. Server/process/network/OS buffers can temporarily hold bytes; this is an application retention promise, not forensic erasure.

Default turns call no detector/model. `use_vision:true` requires intent `category` and one deliberate frame, and uses the existing local NanoDet adapter; candidate categories never select personal identities. General visual questions abstain with `unsupported`. Detector quality remains poor. Unavailable/errors/invalid output/timeouts use manual fallback; Stop/deletion/generation changes discard late output with 409. Provider protocols require cancellation cooperation; no unprovisioned speech adapter runs by default.

Audio input is rejected. Real STT/TTS are unprovisioned; `render_speech:true` reports `not_provisioned` with text fallback. Internal replaceable protocols and explicitly labeled test doubles are not voice acceptance. `confirmed`, `save`, tools/URLs/file destinations/unknown fields are rejected. Remember requires a separate new `/captures` upload and existing explicit reviewed `/commit`; turn content or a spoken/model instruction cannot commit.

`auto` currently renders English wrappers; `fil` renders a bounded Filipino recall wrapper. Recognized `Nasaan [ang|yung] … [ko]?` and `Saan ko [inilagay|nilagay|nailagay|itinago|naiwan] … [ko]?` prefixes are stripped for literal label/alias search. Personal names/locations remain exact saved strings; there is no dictionary translation or general Taglish inference. Negation/actions remain unsupported, ambiguity remains clarify. Confirmed aliases such as `susi` enable that literal query. This is deterministic phrase coverage, not language fluency validation.

## Offline POI primitives (schema version 2)

- `GET /api/poi/cache`: count/generation, caller dataset label, server import time, optional unverified source observation time, unknown source freshness, coverage/limits and OSM attribution. No source is fetched.
- `PUT /api/poi/cache`: explicitly confirmed bounded complete-file snapshot replaces cache atomically. Requires `confirmed:true`, `expected_generation`, `dataset_label`, `snapshot_complete:true`, matching `element_count`, `coverage_bounds:{south,north,west,east}` and 1–250 `elements`. Nodes use `type:"node",id,lat,lon,tags`; ways/relations use `type:"way"|"relation",id,center:{lat,lon},tags`. Supported amenity/shop tags map to an explicit category allowlist. Raw bounded tags are retained. Type+ID prevents collisions; duplicate records, nonfinite/invalid coordinates, unsupported categories, out-of-bounds/incomplete/oversized payloads reject without changing the old cache. Existing 64 KiB JSON limit applies; there is no pack downloader or arbitrary source URL.
- `DELETE /api/poi/cache`: `{confirmed:true,expected_generation}` clears cache and increments generation.
- `POST /api/poi/nearest`: `{confirmed:true,location:{lat,lon,captured_at,accuracy_m},category,max_distance_m:5000,limit:5}`. Timestamp must include timezone, at most 120 seconds old (5-second future tolerance); accuracy must be positive and ≤1000 m. Radius ≤100 km, result limit ≤20. Location fix is caller-supplied, not hardware-verified, and not persisted. Stable haversine calculation scans the bounded cache and orders straight-line distances to cached representative points. No model calculates distances.

Coverage is always declared incomplete, source freshness unknown, and cached matches do not establish current stock, opening hours, routes, emergency suitability or accessibility. Recent import does not imply recent source observation. Empty cache/result means missing cached evidence. OSM contributor/ODbL attribution is returned; source rights remain the importer’s responsibility. No GNSS acquisition, Overpass/GPS transmission, Wi-Fi scheduler, tiles or background sync exists.

Cache uses separate POI tables under the existing SQLite lock; it never participates in personal-item recall. Writes share collection generation to reject stale work. `/api/data` replacement deletes cache and private records together. Retry a cache replacement only after reviewing current generation; unlike personal writes, the cache routes do not promise idempotency receipts. Transactional v1→v2 migration preserves personal records. Product name is undecided; `appbuilderss` is only the working folder label.


## Local browser interface

`GET /` serves the HTML shell; four explicitly enumerated `/assets/` paths serve CSS, app JavaScript, media conversion and the recorder worklet without a session. Only fixed paths in `app/frontend.py` are public for GET/HEAD; arbitrary static paths are not served. API session/CSRF and host/origin checks remain unchanged. The browser obtains `/api/session`, renders user strings as text and uses only same-origin requests. CSP allows local scripts/styles/connections and blob media/images, with no inline/eval or external assets. The API itself retains `default-src 'none'`.

Talk converts deliberate audio to canonical mono16kHz PCM16 WAV (maximum10s), reviews returned transcript and separately confirms `/api/speech/turns`. This does not bypass the existing confirmation contracts. Capture passes raw photo bytes, then commits only after explicit review. Browser retry retains the same idempotency payload in memory after an uncertain response. Reload loses that retry buffer, so the UI/runbook direct the user to inspect Saved before creating another memory. A nonsensitive draft UUID in sessionStorage enables abandoned-photo cleanup on reload; transcripts/audio/photos are not stored in browser persistence. See `DEMO_RUNBOOK.md` and `FRONTEND_IMPLEMENTATION_REPORT.md`.

## Bounded conversational record proposals (2026-10-09 integration)

`POST /api/actions/preview` takes `{ "utterance": "move \"keys\" to \"desk\"" }` and makes no record write. Supported anchored, quoted commands are `remember "name" at "place"`, `move "name" to "place"`, `rename "name" to "new name"`, `categorize "name" as "category"`, and `mark "name" location unknown`. This is `bounded_deterministic`, not open-ended AI chat. Stored descriptions and model output are never interpreted as approval. Names/aliases must resolve exactly and uniquely; existing-name creation and ambiguous records require explicit clarification through Remember.

A proposal contains before/after record fields, operation, proposal ID, exact idempotency key, write epoch, generation and five-minute lifetime. At most 64 are retained in process memory; restart/expiry/cancellation discards them. No proposal text is persisted. `POST /api/actions/{id}/approve` accepts only strict boolean `confirmed:true`, the exact proposal `idempotency_key` and `write_epoch`. Fields cannot be supplied or changed at approval. Existing repository validation and receipts perform the write; generation/revision checks reject stale previews. An uncertain successful approval can replay within the proposal lifetime. After expiry/restart inspect Saved before proposing again. `DELETE /api/actions/{id}` cancels a pending proposal; it does not undo a completed change. Delete-item/delete-all clears ephemeral proposals. Cancellation and approval serialize; whichever commits first wins.

There is no shell, external message, purchase, physical arrangement or general automation action. Speech transcript review is separate from record-change approval. No zero-hallucination or general conversation claim is made.

See `NOOK_NEARBY_BACKEND.md` for the explicit online-download and persisted offline-cache contracts.
