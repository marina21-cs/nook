# Nook architecture and product decisions

Record decisions here before turning them into implementation commitments. Proposed defaults guide experiments; they do not count as resolved choices. Every resolution needs date, owner, rationale, evidence, and affected requirements.

## Adopted scope

| ID | Decision | Status |
| --- | --- | --- |
| A01 | Android-first continuation with memories authoritative on the phone | Adopted from user direction |
| A02 | Cloud AI requires explicit approval; no automatic cloud fallback | Adopted from user direction |
| A03 | Preserve hackathon source and uncommitted work | Adopted |
| A04 | Deliver in appbuilderss; user subsequently authorized Phase 00 fixes and the bounded Expo local-memory slice | Adopted |
| A05 | Use Expo with React Native for production UI; keep inference runtime/model benchmark-gated | Adopted from explicit user direction on 11 October; supersedes the earlier open-UI constraint |

## Resolved framework decision

D03 is resolved on 11 October 2026 by the user: “make sure that we gonna use expo.” The production framework is Expo with React Native. The first feasibility UI is an Expo development build with custom native modules; Kotlin/C++ may implement Android inference internals. The previous Kotlin-only spike and open Compose/React Native/Capacitor comparison are superseded. This is a product decision, not evidence of device performance. Revisit it only through a new explicit scope decision. See [Expo architecture](EXPO_ARCHITECTURE.md).

Affected: phases 00–06, FOLDER_MAP, DEV-01–03, MEM/ACT/AI/UX/SEC/MIG requirements and T01–T05/T09. D04 runtime/model and D14 exact SDK/bridge/build policy remain open. Native UI alternatives remain historical research, not parallel production projects.

## Local continuity and pinned dependency checkpoint

D01 is resolved for local implementation on 11 October under the explicit user authorization: preserve the unborn snapshot, verify the private reviewed ZIP/recovery and isolate mobile work in mobile/expo. The original app remains byte-identical. Ten existing source/config/test paths have narrow authorized changes, listed in implementation-validation.json. No Git mutation occurred. Integration into the published GitHub history remains deferred and requires a reviewed import; this local resolution does not invent a Git HEAD.

D14 is partially resolved: Expo 57.0.27, React Native 0.86.3, React 19.2.3, expo-sqlite 57.0.4, expo-dev-client 57.0.19 and Node 24.19.0 are pinned. TypeScript, SDK dependency check, Hermes bundle, prebuild and disposable configuration reproduction passed. Maintained native configuration stays in plugins; generated android/ios output is ignored. Gradle 9.3.1 and required native artifacts were subsequently provisioned into the owned temporary cache with vendor/publisher checksum evidence. Native compilation progressed, but assembly remains incomplete after Kotlin heap exhaustion and then Gradle 9.3 bundle-producer ordering failure. A corrected native retry is prepared and unrun. AGP 8.12.0/Kotlin 2.1.20/SDK 36/NDK 27.1 are the current diagnostic tuple; merged APK, inference bridge and phone tests remain unqualified. See [build checkpoint](ANDROID_BUILD_CHECKPOINT.md). This does not select llama.cpp or LiteRT-LM. See [milestone evidence](IMPLEMENTATION_RECEIPT.md).

The user explicitly authorized portable foundation work while G00/G01 device prerequisites remain open. Do not mark those release gates closed from the source implementation.

## Open decisions

D15 is resolved by the user's subsequent instruction on 11 October: pause APK/Gradle/native work and establish/test the Expo conversational experience first. Deliver the chat/reminder/capability slice under the [scope addendum](EXPO_CHAT_SCOPE.md). Model quality, first-run provisioning, intentional capture, device notifications and authorized email delivery remain separate adapter/device/provider gates. The prior build checkpoint is historical and must not be resumed from its commands until native work is explicitly requested again. This work creates no model download, permission grant, credentials or email connection.

| ID | Question and proposed starting point | Owner and closing evidence | Blocks |
| --- | --- | --- | --- |
| D02 | First exact phone, OS/ABI, RAM/storage, debugging access and permitted profiling? Prefer a physical 4 GB Android phone first | User/product and engineering; device inventory and access check | Device build settings and all physical tests in 01 |
| D04 | Runtime, model artifact, backend, quantization, context and output caps? Compare llama.cpp and LiteRT-LM with small exact artifacts | Engineering; pinned tuple matrix, quality and resource distributions | Local generation release |
| D05 | Minimum Android/ABI and capability tiers? Do not infer them from total RAM | Product/engineering; named-phone matrix and unavailable-capability behavior | Support policy and G01/G02 |
| D06 | Launch languages, speech targets, latency/cancel/battery criteria and test speakers? English/Filipino/Taglish are evaluation targets | Product/engineering; thresholds registered before tests and language results | Claims and G01/G02 |
| D07 | Cloud provider, audience/age, regions, permitted use, training/retention and sensitive inputs? Gemini consultation selects none | Product/privacy/engineering; current official terms and selected-processing review | 03 and cloud accounts |
| D08 | Monthly/global/per-user budgets, retry policy, storage/versions, deletion SLA and operational owner? | Product/operations; workload forecast, provider billing units, enforceable application stop | 03/04/05 commercial release |
| D09 | Vault protection, crypto library, recovery-secret verification, loss/escrow policy and enrollment? Prefer provider-blind snapshots with explicit recovery secret | Product/security; threat model, reviewed envelope/keys, clean-device recovery exercise | 04 and 05 |
| D10 | Countries, categories, radius, provider/licensing and update cadence for places? Prefer selected-region list-only packs | Product/engineering; permitted source and attribution/distribution design | Places in 02 or 06 |
| D11 | Whether and when to support household sharing, permissions and revocation? Prefer same-user sync first | Product/security; explicit membership, per-record visibility and key design | Household branch of 06 |
| D12 | App license, model/assets redistribution, current visual-reference rights and release disclosures? | Owner/legal/engineering; retained notices and explicit rights/license decision | Public distribution; local synthetic feasibility can proceed |
| D13 | Versioned migration scope, exporter, collision policy, draft handling and supported source schemas? Start with inspected schema 1–4 fixtures after verification | Engineering/user; dry-run report and reversible rehearsal | MIG-01 and G02 |
| D14 | Exact compatible Expo SDK/React Native/Node/JDK/Gradle/NDK versions, native bridge ABI/New Architecture support, CNG/config-plugin policy and local build variants? Prefer local Android builds and reproducible native modules outside generated projects; EAS optional | Engineering; pinned lockfile/configs, module registration/rebuild, generated-project reproduction and standalone offline receipts (01-F11–F13) | First build, G01 and later iOS integration |

## Decision record template

D16 — laptop conversation experiment, 11 October 2026: user-authorized existing Ollama/Qwen only, bounded loopback adapter for Expo web, disabled by default and explicitly enabled per session. Model context excludes the authoritative vault and output has no tools/write authority. See [measured receipt](LAPTOP_CONVERSATION_RECEIPT.md). This does not resolve D04 phone runtime/model, lift D15's native pause or qualify production quality. Requested authoring effort is now High, superseding Max; active metadata is not independently exposed.

- ID and status: open / experiment / resolved / superseded.
- Owner and date.
- Alternatives and the selected option.
- Reason and measured evidence paths.
- Affected requirement IDs, T tests, phases, folder paths, and capability labels.
- Limits, rollback trigger, and re-evaluation condition.

The first device response may resolve D02 while leaving D05 open. A successful runtime test may justify one D04 tuple without qualifying every language or UI. If no model meets the registered target, record the failure and choose a new experiment or narrow advertised tier; local memory remains available.

The evidence record must distinguish a proposed numerical threshold from a measured result and from an approved release target.
