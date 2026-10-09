> Historical baseline document. Its counts, UI steps and provisioning instructions do not describe the expanded release. See [current release and reproduction notes](docs/EXPANDED_RELEASE.md).

## Final Nook UI integration — 9 October 2026, 19:36 UTC

The user approved the finalized UI and explicitly authorized backend wiring. The former UI handoff hold is released by that instruction; no specially named handoff file is required. The authoritative coral opening, mascot, chat and mobile design are preserved. **335 backend tests and 54 browser checks pass on this Nook source**, plus Ruff/formatting, mypy and WAV/JavaScript checks. See [NOOK_INTEGRATION_REPORT.md](NOOK_INTEGRATION_REPORT.md) for scope and evidence. Real speech was not rerun: the fresh guard blocked before launching a model at DIMM 55°C with a high-temperature alarm. No guard was relaxed. Earlier tests/results below remain historical.

# Nook UI/backend synchronization contract — 9 October 2026

## Required final branding

The user finalized **Nook** on 9 October 2026: warm, tactile and physical, evoking everyday places where belongings are set down. Final onboarding, home/chat, page title and other product-name surfaces must use Nook. Aura, Rello and “Local memory” are superseded as product labels; retain earlier reference names only where documenting historical design inputs. Preserve the authoritative styling/reference work. The user has now authorized backend integration of this approved design. Canonical folder, package/API/storage identifiers and release IDs stay unchanged. See [product-name status](docs/PRODUCT_NAME_STATUS.md).

## Ownership — integration authorized by user approval

The user approved the final Nook UI and explicitly requested backend wiring. That instruction releases the previous handoff wait. The backend/release owner integrated and verified the authoritative files in `app/static/`, preserving their design. The separate submission session owns only `submission/nook-v1`; this integration made no writes there. No concurrent application changes were observed during final verification. The previous UI reports are historical; current acceptance is in `NOOK_INTEGRATION_REPORT.md`.

## Existing local integration contract

One FastAPI process serves the UI and API on `http://127.0.0.1:8765/`, bound to loopback. `GET /api/session` returns a CSRF token and sets the HttpOnly session cookie. Every modifying call supplies `X-CSRF-Token`; keep requests same-origin. `GET /api/status` provides `write_epoch`, `generation`, speech provision flags and unavailable visual capabilities. Errors use `{error:{code,message,details}}`.

| Screen action | Route / required payload | State and safety |
| --- | --- | --- |
| Typed recall | `POST /api/recall` with `request_id` UUID, `query`, `use_inference:false` | Read-only; show found/clarify/unknown plus returned evidence. Unknown with items means saved item/location unknown, not item absent. |
| Record one utterance | Browser-started media; `POST /api/speech/transcribe` with request UUID and `{audio:{content_type:"audio/wav",data_base64},language_hint:"auto"}` | Canonical mono16kHz PCM16 WAV, <=10s. Transcript is editable, unconfirmed and ephemeral. Do not auto-submit it. |
| Confirm reviewed voice text | `POST /api/speech/turns` with a fresh request UUID, `utterance`, `transcript_confirmed:true` | Read-only recall/TTS. Manual audio playback; display written result if speech unavailable. Human accuracy and full real browser round trip remain unaccepted. |
| Cancel read/inference | Abort browser request and `POST /api/requests/{request_id}/cancel` | Invalidate late results; stop tracks/context on cancel, navigation/hide and completion. Never request hardware permission during automation. |
| Import deliberate image/frame | `POST /api/captures?source=import` (or camera), raw image bytes with image MIME | JPEG/PNG/still WebP <=10MiB/24Mpx. Draft is not a saved item; response provides id/photo_url/source/timestamps. No continuous capture. |
| Confirm memory | `POST /api/captures/{id}/commit` with `confirmed:true`, idempotency UUID, current write_epoch, rows, location, make_current | New row: `{identity:"new",personal_name}`. Existing: also item_id, expected_revision. Explicit review checkbox/action. `make_current:false` keeps historical evidence. |
| List/review | `GET /api/items?limit=20&offset=0` and `GET /api/items/{id}` | Omit query entirely when empty. Show last-recorded date/source, freshness and unverified current location. Photos from returned authenticated URLs. |
| Location correction | `POST /api/items/{id}/observations` with confirmed write envelope, expected_revision and location string | `location:null` explicitly marks moved/unknown. Old photos stay historical. |
| Delete | Preview `/api/items/{id}/deletion-preview`, then `DELETE /api/items/{id}` with confirmed write envelope, expected_revision, evidence_scope:"unreferenced" | Explicit named-item confirmation. Shared photos remain with other records. On uncertain delete, replay original DELETE directly; do not require preview of an already-deleted item. |
| Discard draft | `DELETE /api/captures/{id}` | Remove abandoned drafts on leave/reload using only a stored UUID; no transcript/photo persistence in browser storage. |

Confirmed write envelope: `confirmed:true`, `idempotency_key:<UUID>`, `write_epoch:<status value>`. Preserve the exact payload/key on a lost response. Prevent double submission; freeze reviewed fields and keep retry accessible until resolved. Do not silently create a new key. On 409, refresh/review before confirming changed data. Cancel cannot undo an already committed write. Inspect Saved after reloading an uncertain result.

No generic model-driven tools, arbitrary shell execution, background sensing, cloud messages or current-location assertions. Render all user/model text as text, not HTML. Existing public asset paths are enumerated in `app/frontend.py`; adding asset paths requires matching safe GET/HEAD exemptions and same-origin CSP. Current CSP excludes inline scripts/styles/eval/external assets. Backend endpoints themselves remain session-protected.

## Acceptance to rerun after the finalized UI lands

Use a temporary store and licensed fixtures. Verify payloads and session bootstrap; true empty/loading/error/success states; explicit transcript/save confirmation; typed fallback; known/unknown/ambiguous/stale evidence; duplicate submissions; lost save/delete responses; cancellation/late callbacks; reload/back/history; no real media permissions; mobile/reflow/keyboard. Existing tests: 335 backend checks and 45 browser checks passed for the previous interface. Their DOM selectors must be adapted to the authoritative final UI, without altering the design.

Current thermal state stopped the extra extracted-source test run at DIMM 54°C. Final real Whisper fixture recognition passed in 9.298s but TTS was stopped for combined swap activity. No guards were changed, no repeated model attempts remain running, and no full-AI acceptance is claimed. Re-run only in an eligible monitored window. Pure contract/document review can continue independently.

## Rubric synchronization

User-supplied judging weights: usefulness25%, LocalAI25%, technical20%, innovation15%, product/demo15%. The LocalAI category requires actual meaningful local inference evidence; disabled-AI or mocked success cannot establish it. Existing typed recall/storage is deterministic and remains useful without speech models, so describe that dependence accurately. Prior real model evidence and the current resource interruption are preserved. No extra model trial or new feature should be introduced while the thermal gate is blocked or the authoritative UI is being edited. The rubric screenshot is not the finalized UI code.

Manual entry, if the authoritative UI already includes it: `POST /api/items` uses the same confirmed/idempotency/write_epoch envelope plus `personal_name`, `location` (string or explicit null), optional aliases/distinguishing_note/category. It must use the same explicit review and uncertain-write protection as photo commit. No new backend feature is needed. Onboarding may store only non-sensitive presentation preferences; it must not imply automatic capture, automatic remembering or model readiness before checking the actual API.
