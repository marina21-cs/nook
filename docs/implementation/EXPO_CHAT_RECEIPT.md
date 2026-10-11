# Nook Expo conversation milestone receipt — 11 October 2026

Result: chat-first source slice implemented and tested without native compilation. The user’s “dont build apk yet” instruction controls the work order. [Scope/PRD reconciliation addendum](EXPO_CHAT_SCOPE.md), [run guide](../../mobile/expo/README.md), [current status](IMPLEMENTATION_STATUS.md).

## Delivered flows

- Chat is the entry point, with readable message history and a visibly labeled deterministic prototype. At most 40 messages live in the JS session; restart/fresh conversation clears context and unsaved previews, preserving confirmed data.
- Narrow natural memory requests produce typed exact previews; an editable manual fallback handles name/place/unknown/date/notes. Explicit buttons approve the exact payload. “Yes” and “save that” do not authorize changes.
- Confirmed source cards retain typed provenance, record ID, observation date and save time. “Last recorded” never implies live location. Missing, unknown and same-name ambiguity are explicit. A selected record ID scopes pronoun/time follow-ups.
- Reminder requests resolve one future date/time with timezone before review. Exact create/cancel operations and durable receipts are atomic. Identical jobs deduplicate and an old create replay cannot resurrect a cancelled reminder.
- In-app reminder requests are stored, not OS-scheduled; due state is displayed while Nook is open. Email is queued locally, not sent. No recipient/account/transport exists, and future delivery requires separate recipient/send approval. Discarded cancellation leaves the request unchanged.
- Setup shows absent sensors/models/providers and the app-managed provisioning contract. It has no simulated capture, model progress, nearby results or readiness. No manual file copying is planned.

The original memory schema, native SQLite adapter, payload semantics and receipt transactions are preserved; the only vault addition is read-only lookup by confirmed ID. Reminder tables have their own additive assistant_schema version 1. Expo web has a separate serialized-operation connection using real SQLite BEGIN/COMMIT because native exclusive transactions are unsupported on web. Web is alpha and browser site storage is a separate vault.

## Actual checks and raw evidence

| Check | Result | Evidence |
| --- | --- | --- |
| Full mobile portable corpus | **43 passed**, 0 failed: 14 original memory tests, 11 interpreter tests, 18 reminder/cancellation tests | [Node log](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-domain-final.log), [guard](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-domain-final-guard.json) |
| Crash/restart and lost response | Real child-process exits before/after memory, reminder and cancellation commits; complete old/new state and exact receipt replay | Same corpus; no repository double substitutes for SQLite |
| Strict TypeScript | Passed | [Source checks](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-static-final.log) |
| Helper/config syntax | 15 JS/CJS files passed node --check; native helpers parsed only, never run | Same source checks |
| Expo dependency check | Passed locally; vendor warns offline validation is unreliable | Same source checks; versions pinned in package/lockfile |
| Expo web export | **287 modules**, real 621,492-byte SQLite WASM and 132,625-byte worker plus app JS | [Final UI export](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-web-export-reflow.log), [guard](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-web-export-reflow-guard.json) |
| Interactive browser | **38 checks passed**, 0 page errors, 0 observed external request attempts | [Results](../../deliverables/nook-expo-chat-20261011-browser-reflow/results.json), [log](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-browser-reflow.log), [guard](../../deliverables/nook-ui-alignment/nook-expo-chat-20261011-browser-reflow-guard.json) |
| Browser storage/offline boundary | Real Expo SQLite worker persists confirmed memories/reminders/cancellation on reload. Loaded-app recall and approved writes work with browser networking disabled | Browser results; no web/phone offline cold-launch claim |
| Visual/accessibility subset | Phone/desktop reviewed; 320px/large-text labels contained and nonoverlapping; buttons/tabs at least 48px | Browser results and screenshots; no TalkBack qualification |

The first basic overflow assertion missed a large-text navigation overlap. Visual review caught it; header/tabs now wrap, and the final test checks text containment, clipping and control overlap. Retain the earlier passing-but-incomplete screenshot evidence rather than treating it as final visual qualification.

Final browser stage maximum owned RSS was 1,146,511,360 bytes, maximum DIMM 50 °C; the unchanged software guard passed. Other stage guards passed. Only project web dependencies were added: pinned react-dom and react-native-web from npm, with install scripts disabled. No model weights or new native dependencies were provisioned.

[Phone chat preview](../../deliverables/nook-expo-chat-20261011-browser-reflow/01-chat-phone.png), [memory approval preview](../../deliverables/nook-expo-chat-20261011-browser-reflow/02-exact-memory-preview.png), [reminder screen](../../deliverables/nook-expo-chat-20261011-browser-reflow/03-reminders-phone.png), [capability screen](../../deliverables/nook-expo-chat-20261011-browser-reflow/04-capabilities-phone.png), [desktop preview](../../deliverables/nook-expo-chat-20261011-browser-reflow/05-chat-desktop.png), [large-text reflow](../../deliverables/nook-expo-chat-20261011-browser-reflow/00-large-text-narrow.png). These are viewport captures of the real exported app; scrollable content continues beyond the viewport.

## Preservation and handoff

The current Git state is unborn master, no HEAD/remotes; all source remains untracked. All 46 original application files and all 160 reviewed source paths outside mobile/implementation docs match the previous checkpoint. The PRD DOCX/Library version 1 is unchanged; the new scope addendum and D15 reconcile the newer instruction. No push, deployment, credential, account connection, permission grant, email, model download, Gradle, prebuild, APK or device install occurred.

Before editing, a private 82-file mobile/implementation-doc snapshot was saved and SHA-256 verified. Current source recovery and the final validation are recorded under [recovery](evidence/20261011/chat/recovery.json) and [validation](evidence/20261011/chat/validation.json). The snapshots exclude credentials, personal vaults, models, dependencies and generated native/build output. No originals are overwritten in recovery rehearsal.

The final browser harness closes its owned server/browser; no dev server or heavy job is left running. The static preview is resumable from its existing export with npm run preview:web in mobile/expo. The [README](../../mobile/expo/README.md) provides guarded test/export commands and Node paths. Earlier native artifacts are stale relative to this UI and must not be used as current UI evidence.

## Unsupported capabilities and next source work

This is not Grok-equivalent generation or a qualified offline model. Real inference/provisioning remains a later development-build/phone/license/resource gate. Camera/photo, voice and nearby data adapters are absent; descriptions are available. No background monitoring exists. Intentional photo intake must normalize/strip metadata, retain reviewed captions and request permission only on user action.

Notifications need a device adapter, permission, reboot/background/timezone tests and reliable cancellation; email needs connectivity, account authorization, a recipient and a separately reviewed payload/send step. The current queue deliberately has no transport. Reminders are single requests, not recurring schedules.

Encryption/export/recovery, edits/deletes, migration and sync are not implemented. Chat remains ephemeral until retained-history export/deletion behavior is specified. Web offline cold reload/service worker is absent. Browser and Node SQLite tests are not native adapter, sensor, model, OS backup, TalkBack, battery or phone performance measurements. G00/G01/G02 remain open. The earlier 528-test Python/31-check hackathon baseline remains historical and was not rerun in this UI-only milestone.

Next legitimate Expo work can refine conversation UX and input/context coverage, with synthetic UI/domain tests. Do not resume the native checkpoint until the user explicitly reauthorizes native work. No product-choice question was needed to complete this source milestone.
