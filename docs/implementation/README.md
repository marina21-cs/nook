# Nook implementation planning

This package organizes the Android-first continuation of Nook into concrete work, checks, tests, and release gates. Expo with React Native is the adopted production framework. The latest user instruction pauses native/APK work and prioritizes the [chat-first Expo source milestone](EXPO_CHAT_SCOPE.md) and its [actual receipt](EXPO_CHAT_RECEIPT.md). Earlier Phase 00 repairs and the typed-memory foundation remain preserved. The existing hackathon application is the behavior reference. Implementation exists in [mobile/expo](../../mobile/expo); see [current status](IMPLEMENTATION_STATUS.md). Physical-device feasibility remains a later gate.

Planning date: 11 October 2026. Confirmed destination: the existing appbuilderss workspace. The latest requested authoring configuration is GPT-6.1 Sol High, superseding Max; this executor does not expose verifiable active-model metadata. The [laptop-local conversation receipt](LAPTOP_CONVERSATION_RECEIPT.md) and [guarded run guide](LAPTOP_CONVERSATION_RUN_GUIDE.md) record the latest implemented source milestone. Native/APK work remains paused.

## Start here

1. Read the [master checklist](MASTER_CHECKLIST.md) and [Phase 00 plan](00-readiness/PLAN.md).
2. Review the [PRD reconciliation](PRD_RECONCILIATION.md), [decision log](DECISIONS.md), and [migration inventory](MIGRATION_INVENTORY.md).
3. Read the [Expo architecture and build plan](EXPO_ARCHITECTURE.md), then use the [folder map](FOLDER_MAP.md) to identify existing behavior references and proposed implementation destinations.
4. Follow the [requirement traceability](REQUIREMENTS_TRACEABILITY.md) and [acceptance catalog](ACCEPTANCE_CATALOG.md). Preserve the PRD identifiers.
5. Record results under the [evidence rules](EVIDENCE_RULES.md); planned tests remain unexecuted until evidence is attached.

## Source PRD

The current editable PRD is [Nook native application PRD.docx](<prd/Nook native application PRD.docx>), revised for the user’s Expo decision on 11 October. Its [extracted text](prd/extracted-text.txt) retains all requirement and acceptance IDs. The [Expo revision record](EXPO_REVISION.md) records visual QA, file integrity and Library writeback.

The original [10 October PRD](<../native-readiness-20261011/prd/Nook native application PRD.docx>) and its [original extracted text](../native-readiness-20261011/prd/extracted-text.txt) are preserved. Library ID remains `libfile_4e7738037b588191a1488fb13bf918df`; version, size and hash for the revision are recorded in [plan-manifest.json](plan-manifest.json).

The PRD includes three Gemini consultation rounds in section 13. Their claims were reviewed against repository evidence and official sources during PRD preparation. Gemini did not select a production framework, establish handset performance, or select the product's cloud provider.

## Phase numbering and dependencies

| Folder | PRD phase | Outcome | Required predecessor gates |
| --- | --- | --- | --- |
| [00 readiness](00-readiness/PLAN.md) | Added checkpoint | Preserve source, establish attributable baseline, resolve initial constraints | None |
| [01 feasibility](01-feasibility/PLAN.md) | 0 Feasibility | Expo development build, custom native adapters, bundled offline slice and named-phone runtime comparison | 00 |
| [02 native local alpha](02-native-local-alpha/PLAN.md) | 1 Native local alpha | Durable private local records, accessible experience, safe migration, qualified capabilities | 00 and 01 |
| [03 optional cloud](03-optional-cloud/PLAN.md) | 2 Optional cloud beta | Approved selected-input cloud answers with enforced budgets | 02 |
| [04 backup recovery](04-backup-recovery/PLAN.md) | 3 Backup and recovery | Verified encrypted export, snapshots, and clean-device recovery | 02 |
| [05 device sync](05-device-sync/PLAN.md) | 4 Device sync | Same-user logical synchronization with conflicts and tombstones | 02 and 04 |
| [06 expansion](06-expansion/PLAN.md) | 5 Expansion | Individually selected platform, household, vision, speech, or place capabilities | 02; household sharing also requires 04 and 05 |

Phases 03 and 04 are independent optional branches after Phase 02. Backup does not require cloud AI. Sync does not require an inference subscription. Expansion is a set of separately scoped choices, not an automatic commitment to every feature.

Each phase has PLAN.md, CHECKLIST.md, TEST_PLAN.md, and EVIDENCE.md. Portable SQLite tests, TypeScript checks, Android bundling and generated-configuration reproduction now have receipts. No complete physical-device or future-service case has passed. G00/G01/G02 remain open; see [Phase 00 evidence](00-readiness/EVIDENCE.md) and [Phase 01 partial evidence](01-feasibility/EVIDENCE.md). The original validation.json is a frozen pre-implementation planning result; implementation-validation.json records the later authorized changes.

## Current checkpoint

The local repository has an unborn `master`, no commits, and no configured remote. GitHub `main` was independently resolved to [1eb0bc7](https://github.com/marina21-cs/nook/commit/1eb0bc7dbc236019a41423c6c9874ae116f4f556) during the readiness turn. The two states must not be conflated. See the safe checkpoint strategy in Phase 00.

Ruff lint/format and combined mypy pass after scoped repairs. The timeout was sandbox-denied Unix self-pipe writes, resolved for tests by allowing local IPC. The current models-off baseline passed 528 tests and 31 cached-browser checks. Failed/historical attempts remain retained, with separate current receipts.

The first handset, Android version/ABI, minimum supported tier, qualified native build/bridge versions, inference engine/model, launch-language claims, cloud provider/audience/budget, recovery policy, and later sharing scope remain open. Phone-dependent tasks wait for handset details. No dates or performance promises are inferred from laptop results.
