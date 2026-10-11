# Nook Android build status — 11 October 2026

**Native/APK work is paused by the user's latest instruction.** No native build is active and no APK is ready. Establish/test the [Expo chat experience](EXPO_CHAT_SCOPE.md) first; see its [receipt](EXPO_CHAT_RECEIPT.md). The prior build results below are historical. Its [recovery commands](ANDROID_BUILD_CHECKPOINT.md) are not authorized for resumption under the current scope.

Gradle 9.3.1 was vendor-checksummed and provisioned under `/tmp/nook-android-build-20261011`. The React Android 0.86.3 release AAR (168,043,847 bytes) matches publisher SHA256. SDK 36/build tools 36.0.0, NDK 27.1.12297006, CMake 3.22.1 and JDK 17.0.18 were already installed. No model weights, new explicit license agreement, account, credential, purchase, push or deployment occurred.

| Stage | Result |
| --- | --- |
| First two configuration attempts | Owned CPU guard stops at 264% / 283%; hardware/guard limits unchanged |
| Configuration with two-CPU owned affinity | Passed in 6m47s |
| Initial native assembly, 384 MiB heap | Failed Expo Kotlin heap exhaustion in 13m53s; no guard violation |
| Native assembly, 512 MiB heap | Kotlin/Java compilation progressed; failed resource packaging in 5m55s because excluded bundle producer outputs cannot be queried under Gradle 9.3; no guard violation |
| Corrected generated source | V3 pool callback registered before eager root plugins; real prebundle verification gate retains producer in graph. Native retry **unrun** |
| Explicit no-clean regeneration | Passed, synthetic marker/prebundle preserved. SDK 57 defaults to recreation without this flag; preceding generated Android output was recreated, maintained source untouched |
| Current static/persistence/prebundle | Passed: Ruff 89 files, mypy 58 source files, strict TypeScript, helper syntax, SDK dependency check (offline limitation), 14 real on-disk SQLite tests, 634-module Hermes asset |
| APK packaging/signature/permissions/ABI/launch | Not established; prepared inspector unrun |

The prior real Hermes asset is 1,602,125 bytes, SHA256 `e7fca681f7b35c18a00a459535d1d31b701ce583f8b84973bcc34e2081a28490`. It predates the chat source changes and is not a current UI artifact or APK. No production or phone support-tier decision is made.

[Machine-readable checkpoint](evidence/20261011/apk/live-build-checkpoint.json), [process cleanup](evidence/20261011/apk/process-cleanup.json), [validation](evidence/20261011/apk/checkpoint-validation.json), [recovery](evidence/20261011/apk/recovery.json). All original 46 app files remain unchanged. Local Git remains unborn master, no HEAD/remotes. Earlier source-milestone tests and attempt logs are retained with their original attribution.

Fresh Library read verified the existing Expo PRD item `libfile_4e7738037b588191a1488fb13bf918df`, version 1, 17 pages, 62,653 bytes. No Library write in this continuation.

Remaining limits: corrected native assembly/inspection; handset D02; installed SQLite/offline/lifecycle/TalkBack/backup transport; runtime/model device comparison; cloud provider/account/cost/security approval. Existing emulator images are x86_64, `/dev/kvm` is absent, and no emulator smoke ran. G00/G01/G02 remain open. No phone performance is claimed.
