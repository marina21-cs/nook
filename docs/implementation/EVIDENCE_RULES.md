# Nook evidence and release records

Every planned capability needs evidence attributable to an exact implementation and environment. These rules govern all phase EVIDENCE.md files and the acceptance catalog.

## Status vocabulary

- **Observed**: an inspection or command result exists; it is not a feature acceptance.
- **Passed**: a completed test met its preregistered condition and has a receipt.
- **Failed**: a completed test missed its condition; retain the failure.
- **Aborted or inconclusive**: the run stopped or lacks a complete result; do not assign a pass count.
- **Not run**: a written future case with no execution evidence.
- **Blocked**: a named prerequisite prevents execution.
- **Historical**: evidence for another source/build; preserve its identity and scope.

CHECKLIST.md may show completed planning work. EVIDENCE.md must not translate it into a product pass. A physical-device requirement cannot be closed by a desktop browser, emulator, fake provider, or vendor example.

## Required receipt

Record test case ID, original PRD T ID, requirement IDs, UTC time, owner, source/build hash, fixture hash/version, command or operator steps, settings, complete outcome, raw evidence paths, cleanup, and deviations. If a command is unavailable before implementation, describe its intended harness; do not invent runnable commands.

For phones, include exact model, OS/build/API, ABI, chipset, total and available RAM, free storage, battery state/health if accessible, ambient conditions, permissions, and connection state. For inference, include runtime commit/build/backend, model hash/license/template/quantization, threads, context/output bounds, prompt lengths, cold/warm classification, and background workload.

For Expo, include SDK/React Native/Node/native bridge versions, New Architecture/ABI, config/lockfile and binary hashes, generated-project reproduction receipt, build variant and update configuration. A Metro-connected development client is distinct from the bundled offline artifact. Native probes/stubs are distinct from real inference. Never infer iOS readiness from the Android build.

Record p50/p95 and complete distributions where specified. Register targets before measuring. A changed target requires a decision entry and new evaluation; it cannot retroactively turn a failure into a pass.

## Privacy and consent evidence

Use synthetic vaults, seeded fake secrets, licensed fixtures, and consented speakers. Separate core no-network runs from approved artifact/area downloads. Capture both app traffic and platform behavior relevant to OS backup, speech, crash reporting, and transfer. Python socket-denial tests establish only their process-scoped boundary.

Cloud consent evidence compares the previewed payload with actual transmitted content and verifies cancellation/off/rejection paths. Backup evidence verifies decryption and restoration; sync evidence preserves conflicts and deletion across stale reconnects. Keep household content and credentials out of logs and public artifacts.

## Gate receipt and resume

A gate record names included/excluded capabilities, device tuples, thresholds, passed/failed/blocked cases, unresolved risks, rollback trigger, last safe source/data snapshot, and approving owner. Preserve prior receipts and update by dated additions rather than rewriting failed history.

After interruption, resume from the last completed verified operation or test step. For uncertain mutation/restore/sync results, inspect the persisted receipt and state before retrying. Do not generate a new idempotency key merely to bypass an uncertain result.

## Planning validation

The package validation checks links, local reference paths, phase-file completeness, dependency ordering, exact PRD requirement coverage, T01–T12 coverage, planned-case cross-references, source preservation, and the PRD hash. It is documentation QA. It does not establish any native/cloud/backup/sync feature pass.

See [validation.json](validation.json) for the final document QA result, and [source-preservation.json](source-preservation.json) for the source inventory protected during authoring.
