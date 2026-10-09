> Historical baseline document. Its counts, UI steps and provisioning instructions do not describe the expanded release. See [current release and reproduction notes](EXPANDED_RELEASE.md).

## Final Nook UI integration — 9 October 2026, 19:36 UTC

The user approved the finalized UI and explicitly authorized backend wiring. The former UI handoff hold is released by that instruction; no specially named handoff file is required. The authoritative coral opening, mascot, chat and mobile design are preserved. **335 backend tests and 54 browser checks pass on this Nook source**, plus Ruff/formatting, mypy and WAV/JavaScript checks. See [NOOK_INTEGRATION_REPORT.md](../NOOK_INTEGRATION_REPORT.md) for scope and evidence. Real speech was not rerun: the fresh guard blocked before launching a model at DIMM 55°C with a high-temperature alarm. No guard was relaxed. Earlier tests/results below remain historical.

| Current UI requirement | Evidence | Result |
| --- | --- | --- |
| Onboarding, appearance, reduced motion | nook_browser_test.cjs persisted reload checks | Pass |
| Explicit photo/manual confirmation, history and unknown | Real HTTP + temporary SQLite/browser checks | Pass |
| Recall, ambiguity, aliases, restart | Real backend, 54 current UI checks | Pass |
| Uncertain save/delete, cancellation, outages | Real mutation + injected transport failures | Pass |
| Voice review/playback/cancel and fallback UI | Explicitly mocked device/provider boundaries | Pass for software wiring only |
| Actual current UI local speech | nook-integration-voice-gate-guard.json | Blocked before launch by thermal alarm |
| Human/Taglish, native phone, general visual accuracy | No corresponding new acceptance | Unverified |

## Natural-query release clarification — 2026-10-09 15:40 UTC

The recognized integrated transcript was exactly **“Blue Keys last recorded at Desk drawer on October 9, 2026. Current location is unverified.”** It correctly transcribed a cached readback statement. Editing to “blue keys” changed that statement into a lookup; it was not a workaround for a broken natural-question parser. “Where are my blue keys?” and arbitrary confirmed aliases work unchanged in deterministic tests. The unchanged description correctly yields the preserved unknown fallback.

38 targeted tests pass, including 14 new generic name/alias/wrapper/ambiguity cases; no production parser change, model run or download. Prior 319 tests remain applicable (333 distinct cases covered across passing batches). Static checks pass (70 formatted files, mypy28).

**Release:** typed natural-question/alias backend and controlled synthetic voice review/edit demonstration are supported. Unchanged natural spoken-query acceptance is still open. The only cached question audio is the known-failed eSpeak fixture. Required human input: a clear consented English recall-question recording (<=10s mono16kHz PCM16 WAV) plus confirmation of its audible content. No claim of human/Taglish or phone readiness. See `VOICE_IMPLEMENTATION_REPORT.md` and `voice/evidence/natural-query-clarification.json`.

---

## Latest integrated laptop acceptance — 2026-10-09 15:34 UTC

**Controlled laptop backend demo ready for the explicit review/edit flow.** Real STT → recorded test-operator transcript edit/confirmation → deterministic seeded-memory recall → real TTS passed through **one persistent worker**. Same PID/start identity across one STT and two TTS calls; false/missing confirmation rejected; unchanged-description unknown fallback spoken; memory generation and all backend file hashes unchanged. Server/worker stopped.

Measured: STT **8.15s**; confirmed recall+TTS **7.67s**; full known chain **15.83s**; unknown fallback **2.06s**; chain plus fallback **17.90s**, excluding human review/audio playback time. Peak sampled process-tree RSS **1.66GiB**, CPU **55.375°C**, DIMM **46.75°C**; unchanged guard passed. This fixture is a spoken description explicitly edited to the lookup label; it does not prove unchanged spoken-question quality. Original eSpeak failure remains unresolved.

319 software tests and final localhost lifecycle/restart pass; no production code changed in this integrated check. Static checks pass (69 files formatted, 28 app files checked). No new downloads; 110,964,538 bytes remain. See `VOICE_IMPLEMENTATION_REPORT.md`, `DEMO_RUNBOOK.md` and `voice/evidence/integrated-chain-1.json`. Human/Taglish quality, general visual conversation and native phone readiness remain open; no frontend/deployment work.

---

## Latest diagnosis and verification — 2026-10-09 15:27 UTC

**319 model-free software tests pass** (138 voice/turn/guard/downloader +181 core). Final real localhost lifecycle/restart gate passes with zero observed Python runtime network attempts and servers stopped. Ruff, formatting (68 files), mypy (28 app files) pass. Earlier resource-interrupted attempts remain historical and are not counted as passes.

Original short eSpeak STT failure remains visible. Fixture reproduction is byte-identical; native events include all five words and completion; PCM decoding, resampling, channels, signal integrity and actual Whisper features show no reproduced implementation defect. Human listening is unavailable, so perceptual clarity is not asserted.

**Independent real TTS passed:** confirmed typed recall yielded 7.725s of 24kHz audio in 14.95s HTTP. **Separate real STT readback passed its content check** in 8.22s, without expected-text hints or decoding changes. Totals: two real STT requests (one failed original fixture, one successful separate fixture), one real TTS request. This is synthetic plumbing evidence, not human/Taglish quality or phone acceptance. `real_inference_accepted` remains false.

All guards retained; downloads unchanged at 1,889,035,462 bytes used, 110,964,538 remaining. See `VOICE_IMPLEMENTATION_REPORT.md` and `voice/evidence/final-checkpoint.json`. General visual conversation and native-phone gates remain unmet; no frontend/deployment work.

---

## Latest acceptance checkpoint — 2026-10-09 15:17 UTC

All approved voice artifacts are verified; offline install, pip check and runtime imports pass. Accounted download total **1,889,035,462 / 2,000,000,000 bytes**, remaining **110,964,538**. Original partials are preserved; no further download is needed.

**Real speech acceptance failed:** the one synthetic-English STT HTTP call returned “Where am I?” for “Where are my blue keys?” in **8,167 ms**. Transcript stayed unconfirmed/ephemeral; zero real TTS calls. Server stopped and model-test resource guard passed. This is not human/Taglish or phone acceptance.

**138 current voice/turn/guard/downloader software tests pass** using explicit fake providers where applicable. Final core reruns were interrupted by swap guards; final localhost lifecycle preflight blocked before server start. No interrupted/unrun check is counted as passed. Prior 290-test and 10,001-edit HTTP results remain historical. Ruff/format/mypy pass. See `VOICE_IMPLEMENTATION_REPORT.md` and `voice/evidence/final-checkpoint.json` for the release matrix and exact evidence.

Remaining blockers: recognition failure needs fixture/provider evaluation before another approved model attempt; recurring host-wide swap requires a quieter window for final core/HTTP checks. Read-only RSS snapshot identifies large indexer/browser/ChatGPT processes without attributing causality or altering them. No thermal/swap limits were relaxed. General visual conversation/native-phone acceptance remain unmet; frontend/deployment remain outside scope.

---

## Latest recovery checkpoint — 2026-10-09 14:35 UTC

Fresh five-sample recovery contained swap-out **4,456,164.32** and **1,748,989.49 bytes/s**, then only two measured zero intervals. This does **not** establish consistently clear swap-out under the latest instruction. No downloader, installation, model call or smoke server was started. DIMMs were **51.0/52.75°C**, CPU **59.75→56.25°C**, available RAM **5.50→5.57 GiB**; the blocker is host-wide swap activity, not a temperature-limit failure. No repeated retry around the resource condition.

Prepared `scripts/voice_download_single.py`: one connection, 32-KiB streaming buffer, maximum 1-MiB validated HTTP ranges, atomic ledger replacement, incremental hashing, complete-file verification and retained original partials. **12,582,912 prefix bytes plus 182,190,080 range bytes** are reusable. Exact remaining payload **301,222,988 bytes** fits remaining allowance **412,285,830 bytes**, leaving **111,062,842 bytes** projected headroom. Accounted total remains **1,587,714,170 / 2,000,000,000**; no transfer occurred this turn. This downloader is prepared, not network-validated.

Preflight now requires four samples containing three measured zero-swap-out intervals, plus all retained temperature/memory/alarm/stability guards. New synthetic downloader/recovery regressions are written but **not run**; final software batches remain behind the authorized real-smoke gate. Current lightweight checks pass: Ruff, formatting (**66 files**), mypy (**28 app files**). Prior 290 core and 111 fake-provider test results describe their earlier snapshots only. Evidence: `voice/evidence/single-stream-recovery.json`, `single-stream-plan.json`. Real voice, visual-conversation and native-phone acceptance remain unmet; frontend/deployment remain outside this phase.

---

## 14:28 UTC provisioning stop

The one authorized voice smoke has not started: provisioning stopped on the retained combined-swap guard. Current budget remaining is 412,285,830 bytes. Latest guard/startup-race/brief-speech regressions are written but not run; prior 290/111 software results retain their stated snapshots. Refer to `../VOICE_IMPLEMENTATION_REPORT.md` for exact sources, bytes, resource readings and pending gates.

---

## Latest voice integration qualification

Audio endpoints and a fixed local CPU worker are now wired in, opt-in and unprovisioned. 111 focused fake-provider audio/worker/turn tests passed after the 290-test core-remediation baseline. Full post-integration software/HTTP reruns and real speech acceptance are pending the unchanged resource gate (last DIMMs 51.5/52.5°C). Do not count provisional provider code as measured inference. See the latest checkpoint in `../DEVIN_FINDINGS_RESPONSE.md`.

---

## 2026-10-09 independent-review regression addendum

| Requirement | Evidence / state |
|---|---|
| Deletion remains possible at receipt capacity | `test_receipt_capacity_never_blocks_privacy_deletion`, actual HTTP receipt stress; schema-v3 write epoch |
| Pruning/reset cannot resurrect writes or erase new records | `test_epoch_rotation_blocks_pruned_create_and_old_reset_replays`, restart QA, real HTTP reset/restart |
| Existing capture commit preserves omission, honors clear/revision | `test_existing_photo_preserves_omitted_metadata_and_explicit_clears`, stale-revision regression |
| Software tests require no model/photo fixture | Separate empty-asset source copy: 290 passed; 15 vision tests excluded |
| Exact confirmed names/aliases containing guard words | Four-name parameterization, duplicate-alias and outside-negation regressions |
| Installable backend with migrations only | Offline pip editable install, outside-source import and three SQL migration resources |
| Verification preserves prior shipped evidence | Default stdout/explicit output and SHA256 comparison |
| DB lock does not stall cancellation; overdue import flagged | Bounded lock heartbeat and freshness tests; reproduced before fix |
| Audio validation, transcript confirmation, no persistence | 64 fake-provider tests pass; routes/providers not yet integrated; real STT/TTS blocked |

Full findings, source evidence and release classifications: `../DEVIN_FINDINGS_RESPONSE.md`. No new model inference or mobile acceptance is represented by this addendum.

---

# Backend requirements to tests — current phase

2026-10-09. Final software/HTTP verification: 213 passed; 15 vision cases excluded; see ../BACKEND_PHASE_REPORT.md. Mock providers are contract tests, not inference acceptance.

| Requirement | Evidence suite / planned check | Release gate |
| --- | --- | --- |
| Explicit reviewed identity/place/provenance, no confirmation bypass | test_contracts, test_capture_lifecycle, test_recall | Implemented + software verified |
| Malformed image/path traversal/strict JSON/session/CSRF | test_backend_qa, test_contracts, test_turns | Implemented + software/HTTP verified |
| Duplicate/ambiguous/moved/stale personal items | test_recall, test_language, test_turns | Exact fields, clarify/unknown preserved |
| Ephemeral utterance + one frame; no implicit remember | test_turns + actual HTTP DB/assets comparison | Typed turn implemented; audio pending |
| Stop races, timeout/provider failure, stale mutations | test_turns, test_forgetting, test_inference | Contract doubles labeled |
| Prompt injection has no write/file/shell/network authority | test_turns, test_language, test_backend_qa | Read-only deterministic execution |
| Language wrapper handling retains exact identity | test_language + API recall | Bounded phrases only; fluency not measured |
| Offline POI type+ID/freshness/coverage/distance | test_poi + actual HTTP import/query/restart | Cached entries only |
| Atomic POI replacement / validation / deletion residue | test_poi + delete-all integration | No location-derived hidden retained cache |
| Real useful detector/general vision | historical VISION_RESULTS / SmolVLM reports | Blocked quality/resource; no mock substitute |
| Embedding retrieval compatible spaces/calibration/index invalidation | Pending selected model/export | Blocked component/measurement decision |
| Actual offline speech/provider licensing/Taglish audio | Pending selected STT/TTS artifacts | Blocked provider choice; no audio route claimed |
| Phone latency/RAM/thermal/GPS/background/accessibility | Pending named 4 GB physical-RAM Android phone/native runtime | Blocked platform/device decision |
| Localhost lifecycle/restart/persistence/concurrency/offline path | phase HTTP script/report; suite socket guards | Laptop-only; no OS isolation claim |
| Frontend, deployment/publication/external agents | None | Deferred by explicit user scope |


## Same-origin local interface — 9 October 2026

| Requirement | Evidence | Status |
| --- | --- | --- |
| Public fixed shell, private API, same-origin assets | `tests/test_frontend.py` | Verified |
| Explicitly confirmed capture; existing/history choice; duplicate protection | `scripts/frontend_browser_test.cjs` real API | Verified |
| Last-recorded, unknown, not-found, ambiguous evidence | Browser suite real recall | Verified |
| Location update/history/delete, reload/restart | Browser suite temporary SQLite/photo store | Verified |
| Lost write response retains receipt payload | Real commit with mocked dropped response, exact replay | Verified |
| Explicit media activation/stop/review/confirmation/playback | Mock media/provider browser tests; canvas camera frame; WAV checks | Interface verified; real hardware unverified |
| Desktop/mobile/keyboard/reflow/dialog | Browser checks and inspected screenshots | Targeted checks passed; no broad accessibility/native claim |
| Human speech, multilingual voice, useful visual retrieval, native phone limits | Prior voice/vision reports | Still unmet; UI is not acceptance evidence |
