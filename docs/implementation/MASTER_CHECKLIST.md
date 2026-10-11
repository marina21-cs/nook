# Nook master implementation checklist

**Current milestone:** the user paused native/APK work and requested the Expo conversational experience first. Follow the [chat scope](EXPO_CHAT_SCOPE.md) and its [receipt](EXPO_CHAT_RECEIPT.md); the release gates below remain open.

This checklist is the route from the preserved hackathon application to a qualified Android-first product. A checked planning task means a document exists; a release gate requires actual implementation evidence and an accountable decision.

## Planning package delivered

- [x] Recover and read the canonical PRD, including Gemini consultation interpretation.
- [x] Reconcile current repository/tooling observations with the PRD.
- [x] Map all 28 requirement IDs and T01–T12 to phases and planned cases.
- [x] Create seven numbered phase folders with plans, checks, tests, and evidence ledgers.
- [x] Define migration inventory, open decisions, source-preservation strategy, and validation.
- [x] Adopt Expo with React Native (D03); revise the PRD and plans for a custom native development build.
- [ ] Pin D14 versions and demonstrate real native builds; Expo selection alone closes no engineering gate.
- [ ] Close engineering readiness; this package does not close Phase 00.
- [x] User authorized Phase 00 fixes and the bounded Expo local-memory slice; source implementation is underway in `mobile/expo/`.

## Phase gates

| Gate | Completion evidence | Status |
| --- | --- | --- |
| G00 | Verified preservation inventory, repository provenance, attributable software baseline, initial device/access constraints | Open |
| G01 | One complete offline slice, named-device measurements, Expo native-module/rebuild and standalone offline results, documented runtime/tier decision or explicit re-scope | Open |
| G02 | T01–T05/T09 for the advertised local capabilities; T10 for included places; migration and recovery verified | Open |
| G03 | T05/T11 plus relevant T12, selected provider terms and budgets, exact-payload consent | Optional, not started |
| G04 | T06/T07/T12, reviewed encryption/recovery design, successful clean-device restore | Optional, not started |
| G05 | T08/T12, causal conflicts, media transfer, deletion and revocation across three clients | Optional, not started |
| G06 | Capability-specific platform/household/vision/voice/place qualification | Optional, not started |

## Phase 00 readiness

- [x] Verify reviewed private source checkpoint and recovery without overwriting originals.
- [x] Diagnose the timeout as sandbox IPC denial; complete 528 current models-off tests and 31 browser checks.
- [x] Repair the formatting issue and 21 script mypy errors; static checks pass.
- [x] Retain historical/failed runs separately from new receipts.
- [ ] Record first phone model, OS/ABI, RAM/storage, device access, and permitted measurements.
- [ ] Record Node/Expo/React Native and Android toolchain compatibility, bridge architecture/ABI, local build variants and exact dependencies (D14).
- [ ] Mark G00 closed only after [Phase 00 checks](00-readiness/CHECKLIST.md) are satisfied.

## Phase 01 feasibility

- [ ] Complete typed save, exact approval, local transaction, restart, and source-backed recall.
- [ ] Exercise ambiguity, unknown location, stale revisions, replay, cancellation, process death, and low memory.
- [ ] Compare pinned llama.cpp and LiteRT-LM tuples with a stable adapter and bounded workload.
- [ ] Measure the named physical phone; extend to the PRD device matrix before a supported-tier claim.
- [ ] Pass 01-F11–F13: native module registration/rebuild on the phone, bundled cold launch without Metro, and reproducible config plugins.
- [ ] Measure Expo UI/bridge overhead, accessibility and lifecycle in the complete inference flow.
- [ ] Resolve D04/D05/D06/D14 or explicitly revise scope; attach G01 evidence. D03 is already resolved.

## Phase 02 native local alpha

- [ ] Implement durable local records, media, approvals/receipts, accessible text flows, and independent capabilities.
- [ ] Rehearse versioned import on copies, including failure recovery, IDs, timestamps, counts, and media hashes.
- [ ] Qualify only the selected local generation/speech/OCR/places capabilities.
- [ ] Pass offline privacy, lifecycle, interruption, denied-permission, and source-authority cases.
- [ ] Complete G02 with device-specific capability labels and recoverable upgrade behavior.

## Later optional phases

- [ ] Phase 03: selected payload consent, server-side secret handling, authorization, cost reservation, quotas, cancellation, outage behavior, and retention/deletion.
- [ ] Phase 04: local encrypted export first where practical, verified recovery secret, last-good backup, clean-device restore, corrupt/wrong-key rejection, deletion.
- [ ] Phase 05: approved local operations first, encrypted logical events, durable outbox, deduplication, causal conflicts, tombstones, media states, revocation.
- [ ] Phase 06: choose one expansion and its prerequisites; maintain core parity and separate capability claims.

## Decisions to close

Consult [DECISIONS.md](DECISIONS.md). D01 is resolved for isolated local work with a verified private checkpoint; upstream Git integration is deferred. D02 blocks physical qualification, while the user authorized the completed local foundation. D03 adopts Expo with React Native. D04 inference remains benchmark-gated; D14 has pinned SDK dependencies but native build/bridge evidence is incomplete. D07–D11 gate their respective optional features. See [actual milestone results](IMPLEMENTATION_RECEIPT.md).

Do not compress optional phases into the alpha because their documents exist. Track a phase as blocked when its prerequisites are missing, and resume from its last verified receipt.
