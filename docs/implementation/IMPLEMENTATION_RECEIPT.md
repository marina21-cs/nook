# Nook first implementation milestone — 11 October 2026

The authorized Phase 00 repairs and smallest Expo local-memory foundation are implemented. The hackathon app is preserved. All full native/device release gates remain open.

This records the first source milestone. Later native dependency/build work and its unresolved packaging failure are in [ANDROID_BUILD_CHECKPOINT.md](ANDROID_BUILD_CHECKPOINT.md); no APK is ready at that checkpoint. The first milestone's hashes and historical results below remain attributed to that milestone.

## Delivered

[mobile/expo](../../mobile/expo) contains the Android-first Expo/React Native application: Remember → exact preview → explicit approval → transactional SQLite save → Saved/dated exact-name Recall. A synchronous UI latch prevents double-tap submission; durable receipts make exact retries idempotent across restart. Changed, expired, cancelled, stale or lost uncommitted previews cannot write. Unknown location, no match and duplicate-name ambiguity remain explicit; stored notes cannot execute actions. Observation time and save time are distinct. There is no general chatbot, inference engine, cloud endpoint, automatic upload or seeded personal memory.

The phone adapter uses real `expo-sqlite` and exclusive transactions. Portable tests use the same schema/repository with real **on-disk Node SQLite**, not an in-memory repository mock. Device qualification of the adapter/UI is still required. The hackathon's approval/receipt/evidence semantics, guard policy, test patterns and palette were reused as references; its web UI and app source were not rewritten.

The editable Expo PRD is [Nook native application PRD.docx](<prd/Nook native application PRD.docx>), Library item `libfile_4e7738037b588191a1488fb13bf918df`, version **1**, 17 rendered/reviewed pages. [The original](<../native-readiness-20261011/prd/Nook native application PRD.docx>) is retained. All 28 requirement IDs and T01–T12 remain in the plans. [Revision evidence](EXPO_REVISION.md).

## Checks at the first source milestone

| Check | Actual outcome | Evidence |
| --- | --- | --- |
| Python collection/timeout diagnosis | 528 collected in 0.40s; TestClient stalled on sandbox-denied asyncio AF_UNIX self-pipe writes; IPC-enabled nine-action diagnostic passed in 0.93s | [diagnostic guard](../../deliverables/nook-ui-alignment/nook-native-20261011-first-test-ipc-guard.json) |
| Current models-off Python baseline | **528 passed in 26.22s**; excludes real `test_vision.py`; one upstream deprecation warning | [test log](../../deliverables/nook-ui-alignment/nook-native-20261011-baseline-repaired.log), [guard](../../deliverables/nook-ui-alignment/nook-native-20261011-baseline-repaired-guard.json) |
| Current browser baseline | **31 checks passed**, real local API, synthetic POI boundary, zero page errors/observed external browser requests | [browser receipt](../../deliverables/nook-native-20261011-web-baseline/browser-results.json) |
| Ruff/mypy | Lint/format pass, 88 formatted files; combined mypy app/scripts passes, 58 source files | [final static log](../../deliverables/nook-ui-alignment/nook-native-20261011-final-static.log) |
| Portable persistence | **14 passed** on Node 24.19.0 LTS and Node 25.8.1; actual child-process exits before memory/receipt commit roll back, exit after commit survives fresh-process recall and exact receipt replay | [LTS log](../../deliverables/nook-ui-alignment/nook-native-20261011-mobile-persistence-lts.log), [guard](../../deliverables/nook-ui-alignment/nook-native-20261011-mobile-persistence-lts-guard.json) |
| TypeScript/Expo dependency check | Strict TypeScript passes; installed dependencies match the pinned Expo SDK | [final static log](../../deliverables/nook-ui-alignment/nook-native-20261011-final-static.log) |
| Android bundle | Metro exported one Hermes bundle, **634 modules**; this is not an APK | [bundle log](../../deliverables/nook-ui-alignment/nook-native-20261011-android-bundle.log), [guard](../../deliverables/nook-ui-alignment/nook-native-20261011-android-bundle-guard.json) |
| First Android prebuild | Passed; generated Android project created without clean-prebuild or device installation | [prebuild log](../../deliverables/nook-ui-alignment/nook-native-20261011-android-prebuild.log) |
| Config reproduction | Nine generated native source/configuration files reproduced byte-for-byte in a disposable copy; source permission removals, backup exclusions and updates-disabled setting checked | [configuration receipt](evidence/20261011/configuration.json), [reproduction guard](../../deliverables/nook-ui-alignment/nook-native-20261011-android-config-reproduction-guard.json) |

Exact commands, source/lockfile/bundle hashes and guard summaries are in [implementation-validation.json](implementation-validation.json). Resource limits were retained. Completed guarded stages had no resource violation; measurements describe this laptop only. The first npm install stopped at its deadline; its cache-assisted bounded resume completed. The initial sandboxed Node test attempt could not use child-process IPC; the IPC-enabled run passed. Failed logs are preserved separately and are not claimed as passes. No app/firewall/OS security setting changed.

## Preservation and scope

Local Git remains **unborn master**, no HEAD/remotes, with source untracked. GitHub main was independently verified during readiness as `1eb0bc7dbc236019a41423c6c9874ae116f4f556`; that does not invent local ancestry. The reviewed private checkpoint contains 204 allowlisted files, ZIP integrity verified and recovery rehearsed without overwriting originals. Personal stores, credentials and model/runtime caches were excluded. A second private source checkpoint now preserves the completed local-memory source, with a verified disposable recovery rehearsal; see [its receipt](evidence/20261011/recovery.json). No Git mutation, push, deployment or model download occurred.

The original 158-path inventory has ten authorized differences: `.gitignore`, one test formatting fix and eight supporting-script repairs. The entire app, Python dependency definitions and remaining original files are byte-identical. Static fixes preserve resource thresholds and outbound-network denial. [Exact difference hashes](implementation-validation.json). The earlier validation.json remains a frozen planning-only receipt.

## Remaining work at that milestone

G00/G01/G02 remain open. The explicit authorization allowed this portable foundation while device gates remain pending. The native wrapper requires **Gradle 9.3.1**, absent from local cached Gradle 8.x distributions; React Native's catalog requests AGP 8.12.0, also uncached, and React/Hermes native Maven artifacts are absent. SDK 36, build tools 36.0.0, NDK 27.1.12297006, CMake 3.22.1 and JDK 17.0.18 are present. Bootstrap/native dependency provisioning and **APK compilation are pending**; no failed APK compile is invented. Generated source checks do not establish the merged manifest or actual OS backup/transfer behavior.

The smallest next milestone is a guarded, serial Android development build with the pinned toolchain, then installation on the identified phone and the typed save/restart/recall flow. The bundled release-mode test remains separate: cold launch without Metro/network, lifecycle/pressure/TalkBack, denied permissions and actual traffic observation. The development manifest retains Internet permission for Metro; the app's core source has no networking path.

The phone model/OS/ABI/RAM/storage/access remain the needed user decision. Inference still needs a licensed-artifact and native bridge experiment comparing llama.cpp and LiteRT-LM on that device; neither engine is selected. No phone latency, memory, battery, offline inference or support-tier claim is made. The first vault is plaintext app-sandbox SQLite with backup exclusions; encryption/recovery, aliases/history/edit/delete, media, import, speech, cloud AI and sync remain later work.
