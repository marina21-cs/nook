# Nook Expo architecture and build plan

The user selected Expo on 11 October 2026. D03 is resolved: production uses Expo with React Native, Android first. The first feasibility UI uses this framework. Kotlin/JNI/C++ may implement Android inference internals; a separate Kotlin/Compose application and a framework comparison are superseded planning proposals. Local AI remains a goal, with the runtime, model, languages and supported tier gated by physical measurements. Cloud AI remains separately approved.

This plan now has a bounded implementation in mobile/expo: pinned dependencies, typed memories, SQLite approvals/receipts and exact recall. Portable persistence tests, TypeScript, Android bundling and first prebuild passed. No APK, installed-device or inference result exists yet. [D14](DECISIONS.md) records pinned versions and the remaining native toolchain/bridge gate; [the receipt](IMPLEMENTATION_RECEIPT.md) distinguishes each check.

## Development client and offline artifact

| Artifact | What it establishes | Nook use |
| --- | --- | --- |
| Expo Go | Runs JS against its fixed, precompiled set of native libraries; it cannot gain an arbitrary native inference library through a JS refresh | Optional UI-only exploration cannot qualify Nook inference or its installed permission configuration |
| Expo development build with expo-dev-client | Nook's own native binary with its included libraries/modules; normally connects to Metro for development JS | First native module registration, rebuild, device integration and workflow development |
| Bundled release-mode test artifact | Includes application JS/assets and the same native adapters; can be tested without Metro | Airplane cold start, restart, persistence, private-network capture and release-relevant measurements; signing/distribution remain separate |

Expo describes the fixed Go runtime and the distinction between Metro-served development JS and bundled production JS. Native code, dependencies or configuration changes need a rebuilt native binary; JS refresh alone is insufficient. The development-client result and the standalone offline result receive separate evidence receipts. [Development-build FAQ](https://docs.expo.dev/develop/development-builds/faq/), [development-build introduction](https://docs.expo.dev/develop/development-builds/introduction/).

## Component responsibilities

| Proposed destination | Responsibility and boundary |
| --- | --- |
| `mobile/expo/src/` | TypeScript domain, trusted preview/approval, local repository/retrieval, accessible React Native screens and capability routing |
| `mobile/expo/modules/nook-ai/` | Platform-native artifact status, load/generate/cancel/release interface; small validated inputs, text/progress/errors returned to JS |
| Module `android/` and optional `cpp/` | Android Kotlin/JNI/C++ runtime internals; llama.cpp and LiteRT-LM compared behind a stable contract, not chosen by framework adoption |
| Module `ios/` or another qualified adapter | Later Swift/native integration; Android binaries do not establish iOS support |
| `mobile/expo/plugins/` | Reproducible build configuration for native dependencies, manifest permissions and backup exclusions |
| `mobile/expo/android/`, `mobile/expo/ios/` | Generated native build projects under the proposed CNG policy; maintained custom sources stay in modules/plugins |
| `tests/native/`, `evidence/native/` | Portable contract corpus and attributed device/build/ABI/runtime measurements |

Expo Modules supports Kotlin/Swift and the New Architecture. Expo specifically recommends considering TurboModules for substantial C++ interop. Therefore D14 must choose and prove the bridge packaging: an Expo Modules platform wrapper with a reviewed native binding, or a compatible TurboModule/JSI integration. Neither llama.cpp nor LiteRT-LM is assumed to be a ready-made Expo plugin. Keep tensors, model weights and execution inside native code; generation should run off the UI thread, with bounded progress, cancellation and cleanup. The last sentence is Nook's design requirement, to be measured in F05/F09/F11. [Expo Modules overview](https://docs.expo.dev/modules/overview/), [local-module structure](https://docs.expo.dev/modules/get-started/).

Use one model session initially. Runtime/model/backend/quantization/context/output/threads remain D04 choices; record full tuples. A native-module probe or mock result proves integration only. Actual inference requires separately authorized licensed artifacts and F05's device workload. On a missing, unsupported or failed module/model, deterministic source-card recall and text edits remain available; cloud routing is never an automatic fallback.

## Persistence and permissions

Evaluate `expo-sqlite` for the authoritative phone database; it persists across app restarts and supports Android/iOS. Store approvals, operations, revisions and receipts transactionally. Review the selected transaction API's concurrency semantics rather than assuming every async query is scoped to an intended transaction. Optional SQLCipher/FTS build settings need native configuration; encryption is a separate D09 design, not supplied by choosing SQLite. [SQLite documentation](https://docs.expo.dev/versions/latest/sdk/sqlite/).

Use app-owned durable file locations for confirmed media and model manifests; temporary cache files are not authoritative records. Journal DB/media activation, verify hashes and preserve the last complete state on interruption. Recheck the selected API's semantics, app uninstall and OS backup/transfer rules during implementation. [FileSystem documentation](https://docs.expo.dev/versions/latest/sdk/filesystem/).

SecureStore is a candidate for small protected secrets, not the record database or a complete vault-encryption design. Android uninstall loses its entries; iOS Keychain behavior differs and is not a recovery guarantee. Android backup must exclude undecryptable SecureStore entries, and Nook must also review vault/media backup rules. Do not infer provider-blind recovery from a library name. [SecureStore documentation](https://docs.expo.dev/versions/latest/sdk/securestore/).

Standalone and development builds need build-time permission configuration as well as runtime requests. Inspect merged Android permissions contributed by dependencies; remove unjustified ones. The text-first slice needs no camera/microphone/location prompt. Test grant, denial, revocation and background/process death in Nook's installed binary; Expo Go's permission environment cannot qualify them. Each later media/speech/location feature remains user-invoked and optional. [Permission guidance](https://docs.expo.dev/guides/permissions/).

## Local builds and native configuration

Local Android builds use the installed Android SDK/JDK and compatible Node/Expo toolchain; Expo account/EAS is not required for that route. EAS cloud builds are optional. The design imposes no paid EAS requirement. The pinned SDK dependencies pass Expo compatibility checks and TypeScript/bundling; generated configuration reproduces. Gradle 9.3.1 and required native Maven artifacts are not cached, and APK compilation is pending. The commands below have not run. [Development-build introduction](https://docs.expo.dev/develop/development-builds/introduction/), [local app development](https://docs.expo.dev/guides/local-app-development/).

Later command examples, after project creation, pinning and authorized provisioning:

~~~sh
# From the future mobile/expo project; builds/installs and starts Metro.
npx expo run:android --device
# Separate bundled release-mode test; not a store-ready signed release.
npx expo run:android --variant release --device
~~~

Record the connected phone and chosen device explicitly, source/config/lockfile hashes, ABI, native library and bridge versions, build variant and artifact hash. Local iOS builds require macOS/Xcode, unavailable on this Linux executor. Optional EAS can compile remotely; device signing/provisioning and any account/credentials remain separately scoped. [Local production builds](https://docs.expo.dev/guides/local-app-production/).

Proposed Continuous Native Generation uses app configuration/config plugins to reproduce native projects. Keep maintained native code outside generated directories. Clean prebuild can delete those directories and lose direct edits; reproduce only in a disposable copy after preservation, never as a checkpoint operation here. Commit policy and exact dependency setup close under D14. [CNG guidance](https://docs.expo.dev/workflow/continuous-native-generation/).

## Offline and optional networking

Ship/test an embedded JS bundle and provisioned local assets. For the feasibility offline artifact, omit remote update integration or explicitly disable update checks with verified build configuration. If Expo Updates is later adopted, version/ABI compatibility, update consent/network policy and recovery need an explicit decision; JS updates cannot supply new native libraries. Expo documents embedded bundles and configurable update networking. All cloud AI/backup/sync/nearby controls remain independent; EAS build service and app update traffic are not AI consent. [Updates documentation](https://docs.expo.dev/versions/latest/sdk/updates/).

Test the bundled artifact with Metro stopped, Wi-Fi/mobile data unavailable, after cold launch and reboot, using a synthetic vault. Cover missing model, approved-write replay, stale revision, no-match, ambiguity and unknown location. Capture traffic separately in an online network-observation run with all optional services off; airplane mode alone cannot prove the absence of attempted requests. A successful dev-client flow with Metro reachable cannot close this offline gate.

## Integration exit evidence

G01 remains open. F11 establishes physical install, native registration, ABI/architecture and rebuild behavior. F12 establishes bundled offline local records and privacy. F13 establishes reproducible config/plugins and preservation of maintained native code. F05/F09 measure runtime and full Expo UI/bridge behavior; they remain separate from build success. Original T01–T12 and all 28 requirement IDs are retained in [traceability](REQUIREMENTS_TRACEABILITY.md).

The phone, compatible Expo/native version tuple, runtime/model, supported-device tier and thresholds still need decisions. No handset performance, iOS readiness or cloud-provider selection follows from the Expo decision.
