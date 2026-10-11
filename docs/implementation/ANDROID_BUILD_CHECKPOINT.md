# Nook Android build checkpoint — 11 October 2026

**Current scope override:** the user subsequently said “dont build apk yet.” All native retry commands below are historical recovery evidence and must stay paused. Continue the [Expo chat scope](EXPO_CHAT_SCOPE.md) and [source/test receipt](EXPO_CHAT_RECEIPT.md).

**No APK is ready. All owned build/test stages have ended.** The parent requested this safe checkpoint so implementation can resume in the next turn; implementation is not cancelled.

At this historical build checkpoint, the app was typed object → exact preview → explicit save → transactional SQLite memory/receipt → restart → dated exact-name recall. Its app/domain/storage code was unchanged during that build continuation. The later chat-first source milestone changes the Expo UI and adds reminder tables; it does not resume this native build. Existing previews remain ephemeral; confirmed receipts survive restart. The preserved hackathon app has all 46 original application files byte-identical.

## Completed work and results

- Official Gradle **9.3.1** provisioned under `/tmp/nook-android-build-20261011`. Vendor checksum and ZIP CRC verified: [bootstrap receipt](evidence/20261011/apk/build-tools.json). Required ordinary native artifacts resolve into the owned Gradle cache. The **168,043,847-byte React Android release AAR** matches publisher SHA256: [artifact receipt](evidence/20261011/apk/react-android-release-artifact.json). No model weights, new SDK license agreement, credentials, account, purchase, push or deployment occurred.
- Gradle configuration passed in **6m47s** after the two earlier owned-CPU guard stops. Own-tree affinity is two allowed CPUs, Gradle workers one, JVM-visible processor one. The hardware/RSS/CPU/swap thresholds remain unchanged.
- Initial native assembly failed in **13m53s** at `:expo-modules-core:compileReleaseKotlin`: `OutOfMemoryError: Java heap space` with a 384 MiB heap. The guard was not violated; maximum tree RSS 1,193,119,744 bytes.
- A bounded **512 MiB heap / 384 MiB metaspace**, 64 MiB launcher retry passed the native C++ and Kotlin/Java tasks reached before packaging. It failed in **5m55s** at `:app:mapReleaseSourceSetPaths`: Gradle 9.3 could not query generated resources because `:app:createBundleReleaseJsAndAssets` had been excluded with `-x`. Maximum tree RSS 1,466,036,224 bytes; guard not violated. Neither failure is a permission block.
- Maintained fixes are prepared: register CMake pool callbacks **before** root plugins eagerly evaluate `:app`; apply at DSL finalization; keep the bundle producer task in the graph and skip generation only after hashing the actual staged Hermes asset and current source. The old `-x` argument is removed. **The corrected native retry has not run**, so its Gradle behavior and app pool effectiveness remain unqualified.
- The pinned SDK 57 prebuild defaults to recreating generated native folders. A preceding regeneration cleared generated Android output; maintained source and library caches remained intact. The script now explicitly uses **`--no-clean`**. A bounded preservation rehearsal kept the synthetic marker and exact prebundle; V3 regeneration reused the native folder. No manual native edits were present. All 46 original app files were rechecked unchanged.
- Fresh static checks passed: Ruff lint/format (**89 files**), combined mypy app/scripts (**58 source files**), strict TypeScript, syntax checks for plugin/build helpers, and the SDK dependency check. The latter reports its offline-mode limitation. [Static log](../../deliverables/nook-ui-alignment/nook-native-20261011-build-checkpoint-static.log).
- Fresh **14 real on-disk SQLite/restart/approval tests passed** on Node 24.19.0. Actual fresh-process crash/receipt replay remains covered. These do not qualify the installed Android adapter. [Test log](../../deliverables/nook-ui-alignment/nook-native-20261011-build-checkpoint-persistence.log).
- Current real Hermes prebundle passed: **634 modules, 1,602,125 bytes**, SHA256 `e7fca681f7b35c18a00a459535d1d31b701ce583f8b84973bcc34e2081a28490`. [Source/command receipt](evidence/20261011/apk/prebundle-checkpoint-v3.json). It is not an APK.
- Fresh Library read confirmed existing PRD item `libfile_4e7738037b588191a1488fb13bf918df`, **version 1**, 17 pages, 62,653 bytes, with Expo/React Native content. No Library write in this continuation. [Verification](evidence/20261011/apk/prd-library-verification.json).

Current versions: Expo 57.0.27, React Native 0.86.3, React 19.2.3, expo-sqlite 57.0.4, expo-dev-client 57.0.19, Node 24.19.0, JDK 17.0.18, Gradle 9.3.1, AGP 8.12.0, Kotlin 2.1.20, KSP 2.1.20-2.0.1, compile/target SDK 36, diagnostic minimum SDK 24, build tools 36.0.0, NDK 27.1.12297006 and CMake 3.22.1. Resolved Hermes Android metadata is 250829098.0.17. These establish the build tuple, not a supported-phone policy.

The earlier full baseline remains **528 models-off Python tests and 31 browser checks passed**, attributed to [the first source milestone](IMPLEMENTATION_RECEIPT.md). Its timeout was sandbox-denied asyncio Unix self-pipe writes; permitted local test IPC resolved it without app/dependency/security changes. Those suites were not needlessly rerun in this build continuation because their app source remains unchanged.

## Safe resume

No heavy work is left running. Previous build sessions completed and guards cleaned up their owned process groups; the final validation record confirms process cleanup. Do not reuse completed evidence stage names. Ordinary native dependency provisioning remains authorized; SDK/Java auto-provisioning is disabled. `/tmp` inputs must be checked for continued availability on resume.

From `/home/keni/Documents/ChatGPT/appbuilderss`, the current prebundle is already fresh. If its source changed, regenerate with a new stage name:

```sh
.venv/bin/python scripts/software_guard.py --stage nook-native-20261011-resume-v3-embed --timeout 240 -- /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/bundleAndroidLimited.mjs
```

Then run the **unrun corrected** native attempt through the reviewed execution route (local Gradle IPC and recognized vendor registries):

```sh
.venv/bin/python scripts/software_guard.py --stage nook-native-20261011-resume-v3-assemble --timeout 1200 -- /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/buildAndroidLimited.mjs release /tmp/nook-android-build-20261011/gradle-9.3.1/bin/gradle /home/keni/Android/Sdk /tmp/nook-android-build-20261011/gradle-home
```

The wrapper refuses stale source/bundle bytes. Keep supervising the guard; diagnose a new failure and preserve its distinct receipt. Do not increase guard thresholds, accept a new explicit legal agreement, create credentials or start a device silently. Confirm the app and library metadata/build.ninja actually contain the pool flags, and confirm the producer-task verification works under Gradle 9.3.

If assembly succeeds, its expected generated output is `mobile/expo/android/app/build/outputs/apk/release/app-release.apk` (currently absent). Then run static artifact inspection:

```sh
.venv/bin/python scripts/software_guard.py --stage nook-native-20261011-resume-v3-inspect --timeout 120 -- .venv/bin/python mobile/expo/tools/inspectAndroidArtifact.py mobile/expo/android/app/build/outputs/apk/release/app-release.apk /home/keni/Android/Sdk mobile/expo/android/.nook-prebundled-release.json deliverables/nook-native-20261011-apk-v3
```

The prepared inspector verifies ZIP/signing/alignment, package/SDK/permissions/backup flags, the exact embedded Hermes bytes and ARM64 ELF libraries; records artifact path/hash; never installs. It has not inspected an APK yet. The intended APK is a release-mode **ARM64 diagnostic with the existing public template debug key**, not production signing or a device-tier choice.

After a verified APK, continue feasible durable-review/restart/error/accessibility work and meaningful persistence regressions. Preserve the old source milestone and distinguish portable subsets from full physical acceptance. No permanent inference engine/model is selected.

## Remaining qualification and preservation

Local Git is **unborn `master`**, no HEAD/remotes, all source untracked. The original 158-path inventory still has only the ten previously authorized differences; no new changes to those original paths in this continuation. A new private reviewed source checkpoint and disposable recovery rehearsal are linked in [recovery.json](evidence/20261011/apk/recovery.json); it excludes personal stores, credentials, models, installed dependencies and generated native/build output. [Final continuation validation](evidence/20261011/apk/checkpoint-validation.json) and [machine-readable status](evidence/20261011/apk/live-build-checkpoint.json) record the exact attempts, source hashes, checks and process state. Earlier receipts remain historical.

Exact open limits: corrected native build/packaged manifest/signature/ABI checks unrun; no emulator smoke (existing x86_64 images, `/dev/kvm` absent); handset model/OS/ABI/RAM/storage/access pending D02; installed SQLite/offline launch/lifecycle/TalkBack/backup transport unrun; llama.cpp versus LiteRT-LM remains a named-device/licensed-artifact experiment; cloud provider/account/cost/security decisions need approval. G00/G01/G02 remain open. No phone performance or release readiness is claimed.
