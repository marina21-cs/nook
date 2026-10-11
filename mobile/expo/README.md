# Nook — Expo conversation milestone

Nook is an Android-first Expo/React Native personal-assistant prototype, isolated from the preserved Python/web hackathon app. The current milestone is the conversational experience. **APK, Gradle, prebuild and device-install work are paused by the user.** The earlier [native build checkpoint](../../docs/implementation/ANDROID_BUILD_CHECKPOINT.md) is historical.

Use Node **24.19.0** from .node-version. Expo 57.0.27, React Native 0.86.3, React/React DOM 19.2.3, React Native Web 0.21.0, expo-sqlite 57.0.4 and expo-dev-client 57.0.19 are pinned in the lockfile.

## Run and test without compiling Android

From this directory, with the existing dependencies:

~~~sh
npm run typecheck
npm test
npm run check:dependencies
npm run export:web
npm run preview:web
~~~

The static preview opens at http://127.0.0.1:8081. It serves the required SQLite isolation headers and binds only to localhost. Stop it with Ctrl+C. Choose a different unused port with npm run preview:web -- 8082. The preview uses actual Expo SQLite's WASM worker; web support is alpha. Browser site data is separate from the Android app vault. Clearing browser site data removes the preview records.

npm run web starts Metro for interactive web development; metro.config.cjs supplies the same isolation headers. npm start requests Expo Go for its supported text/SQLite libraries. No handset session or Expo Go phone qualification has been run. The later custom inference module requires a separately authorized development build: Expo Go cannot load arbitrary added native runtimes. [Expo web](https://docs.expo.dev/workflow/web/), [SQLite web setup/transaction limits](https://docs.expo.dev/versions/latest/sdk/sqlite/), [development builds](https://docs.expo.dev/develop/development-builds/introduction/).

In the managed executor, keep resource guards and the established test-local IPC route:

~~~sh
# From the repository root, using a new evidence stage name for each run:
.venv/bin/python scripts/software_guard.py --stage nook-expo-chat-domain-next --timeout 120 -- /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --test --test-concurrency=1 mobile/expo/tests/conversation.test.mjs mobile/expo/tests/reminders.test.mjs mobile/expo/tests/vault.test.mjs

.venv/bin/python scripts/software_guard.py --stage nook-expo-chat-web-next --timeout 240 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/exportWebLimited.mjs

NOOK_BROWSER_OUTPUT=deliverables/nook-expo-chat-browser-next .venv/bin/python scripts/software_guard.py --stage nook-expo-chat-browser-next --timeout 180 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tests/browserFlows.mjs
~~~

The portable corpus uses real on-disk Node SQLite, with actual child-process exits before/after memory, reminder and cancellation commits. Browser flows use the exported React Native Web app and real SQLite WASM/worker persistence. They close their owned browser/server. A fresh output directory is required. Neither test path qualifies Android storage/lifecycle, native inference or TalkBack.

## Try the flows

- “Remember my keys are in the hall drawer” → exact preview → edit if needed → Save this exact memory.
- “Remember keys are on the shelf; seen 2025-01-01T09:15:00Z” preserves the earlier observation date.
- “Where are my keys?” shows confirmed source cards. Multiple same-name records require a selection; unknown and missing stay explicit.
- “When did you see it?” follows the selected record ID and labels the time as user-reported.
- “Remind me to water plants in 10 minutes” resolves one date/time and proposes a local request.
- “Email me to check the bill at 2026-11-01T09:00:00+08:00” proposes an explicitly unsent local email-queue request.
- Use Reminders → Review cancellation → Confirm this cancellation, or discard the preview.
- “Look around,” “Use voice,” “Set up offline AI” and “What shops are near me?” show honest unavailable states.
- Enter memory details supplies the manual fallback if the narrow grammar cannot express a request.

The memory/reminder interpreter is deterministic and visibly labeled. General questions receive a prototype explanation by default. An optional session-approved laptop-local Qwen adapter now works in the web preview: use the [guarded run guide](../../docs/implementation/LAPTOP_CONVERSATION_RUN_GUIDE.md), then Setup → Enable laptop conversation. Generated replies have a separate label and no vault, notes, tools or mutation authority. Typed actions still require exact approval buttons. [Actual laptop evidence](../../docs/implementation/LAPTOP_CONVERSATION_RECEIPT.md) is separate from synthetic UI fixtures and phone qualification.

## Persistence and limits

The authoritative database is app-owned nook-local-memory-v1.sqlite. Original memory tables, schema version 1 and durable exact approval receipts retain their tested semantics. Reminder tables use a separate additive assistant_schema version 1. Creation/cancellation and their receipts commit together. Exact retries deduplicate; cancellation cannot be undone by replaying an older create receipt.

Memory observation and save times stay distinct. “Last recorded” is a past observation, not live location. Raw notes are inert text. No sample records are seeded. Previews expire after five minutes and disappear on JS/process restart. Committed memories and reminder/cancellation receipts persist. Chat history/context stays in the JS session, bounded to 40 messages, and can be cleared without removing confirmed data.

Local reminders are **stored, not scheduled as device notifications**. Due status appears while Nook is open. Email is **queued locally, not sent**; no recipient/account/transport exists. Delivery will require connectivity, authorization and a separate exact recipient/send review. Recurring reminders, device alarms/background delivery and email retries are not implemented.

Phone-local AI, voice, intentional photos/camera, nearby data, cloud AI, vault encryption, export/recovery, edits/deletes, migration and sync remain adapter/device/security gates. No model is downloaded. The Setup screen and [scope contract](../../docs/implementation/EXPO_CHAT_SCOPE.md) describe app-managed provisioning with consent, exact sizes, storage checks, progress/retry, verification and readiness before any “ready offline” claim.

SQLite is plaintext in local app/browser storage. No phone performance, offline cold launch, background capture, email delivery or packaged privacy qualification is claimed. The loaded browser app can operate with browser networking disabled; a service-worker/offline browser cold reload is not implemented.

Read [the current evidence receipt](../../docs/implementation/EXPO_CHAT_RECEIPT.md) and [implementation status](../../docs/implementation/IMPLEMENTATION_STATUS.md). Native configuration stays in maintained plugins; generated android/ios projects remain ignored and unchanged by this milestone.
