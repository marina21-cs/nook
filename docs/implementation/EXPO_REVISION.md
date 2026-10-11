# Nook Expo revision record

On 11 October 2026 the user selected Expo. The plans and editable PRD adopt Expo with React Native as the production framework and replace the Kotlin-only feasibility UI with an Expo development build containing custom native modules. Kotlin/C++ may still implement Android runtime internals. The original PRD is preserved at [its recovered path](<../native-readiness-20261011/prd/Nook native application PRD.docx>).

The [current local PRD](<prd/Nook native application PRD.docx>) updates the product recommendation, framework/component boundaries, build/offline/permission plan, phase-0 deliverable, decisions, test prerequisites and Expo sources. Comments at the affected decisions identify the revision. All 28 original requirement IDs and T01–T12 remain intact. Phone performance, runtime/model, exact SDK versions and cloud provider remain undecided.

Planning changes include the new [Expo architecture](EXPO_ARCHITECTURE.md), D03 resolution and D14 build/integration decision, consistent proposed `mobile/expo/` destinations, revised phase plans/checklists/evidence, and F11–F13 integration cases with updated traceability. No application project is scaffolded and no application test is rerun.

## Verification and Library result

Document integrity and full visual QA passed for the 17-page revision using the bundled DOCX renderer. Every page was inspected at original resolution; already inspected pages were reused only when their final PNG bytes matched exactly. Six margin comments identify changed decisions. The [manifest](plan-manifest.json) records size 62,653 bytes and SHA256 `ae6de6a20532963337f4c038096637818bbe114940a70c71d06115bc1052043c`. The [validation report](validation.json) records all original IDs, cases, links and pre-implementation source preservation checks.

The same Library item `libfile_4e7738037b588191a1488fb13bf918df` was successfully replaced with expected version 0 and is now version 1 at `/Nook native application PRD.docx`. Local Library identity/version metadata was persisted. No separate item was created. The original version-0 local bytes remain unchanged.

This verification checkpoint precedes the subsequently authorized implementation. Later application results belong in the phase evidence ledger; the PRD revision itself makes no implementation or handset-performance claim.

## Exact planning paths changed

- [00-readiness/CHECKLIST.md](<00-readiness/CHECKLIST.md>)
- [00-readiness/EVIDENCE.md](<00-readiness/EVIDENCE.md>)
- [00-readiness/PLAN.md](<00-readiness/PLAN.md>)
- [00-readiness/TEST_PLAN.md](<00-readiness/TEST_PLAN.md>)
- [01-feasibility/CHECKLIST.md](<01-feasibility/CHECKLIST.md>)
- [01-feasibility/EVIDENCE.md](<01-feasibility/EVIDENCE.md>)
- [01-feasibility/PLAN.md](<01-feasibility/PLAN.md>)
- [01-feasibility/TEST_PLAN.md](<01-feasibility/TEST_PLAN.md>)
- [02-native-local-alpha/CHECKLIST.md](<02-native-local-alpha/CHECKLIST.md>)
- [02-native-local-alpha/EVIDENCE.md](<02-native-local-alpha/EVIDENCE.md>)
- [02-native-local-alpha/PLAN.md](<02-native-local-alpha/PLAN.md>)
- [02-native-local-alpha/TEST_PLAN.md](<02-native-local-alpha/TEST_PLAN.md>)
- [03-optional-cloud/PLAN.md](<03-optional-cloud/PLAN.md>)
- [04-backup-recovery/PLAN.md](<04-backup-recovery/PLAN.md>)
- [05-device-sync/PLAN.md](<05-device-sync/PLAN.md>)
- [06-expansion/CHECKLIST.md](<06-expansion/CHECKLIST.md>)
- [06-expansion/EVIDENCE.md](<06-expansion/EVIDENCE.md>)
- [06-expansion/PLAN.md](<06-expansion/PLAN.md>)
- [06-expansion/TEST_PLAN.md](<06-expansion/TEST_PLAN.md>)
- [ACCEPTANCE_CATALOG.md](<ACCEPTANCE_CATALOG.md>)
- [DECISIONS.md](<DECISIONS.md>)
- [EVIDENCE_RULES.md](<EVIDENCE_RULES.md>)
- [EXPO_ARCHITECTURE.md](<EXPO_ARCHITECTURE.md>)
- [EXPO_REVISION.md](<EXPO_REVISION.md>)
- [FOLDER_MAP.md](<FOLDER_MAP.md>)
- [MASTER_CHECKLIST.md](<MASTER_CHECKLIST.md>)
- [PRD_RECONCILIATION.md](<PRD_RECONCILIATION.md>)
- [README.md](<README.md>)
- [REQUIREMENTS_TRACEABILITY.md](<REQUIREMENTS_TRACEABILITY.md>)
- [plan-manifest.json](<plan-manifest.json>)
- [prd/Nook native application PRD.docx](<prd/Nook native application PRD.docx>)
- [prd/extracted-text.txt](<prd/extracted-text.txt>)
- [validation.json](<validation.json>)
