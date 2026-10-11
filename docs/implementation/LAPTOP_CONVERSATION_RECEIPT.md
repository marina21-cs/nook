# Nook laptop-local conversation — 11 October 2026

Implemented in the existing Expo web source, preserving the hackathon app and exact memory/reminder approvals. The user authorized existing Ollama/Qwen only and requested GPT-6.1 Sol High; active model/effort metadata is not independently exposed. Native/APK work stays paused. This laptop experiment does not choose phone inference or establish production qualification.

## Delivered behavior and boundaries

Setup offers **Enable laptop conversation** for this web session. Default is disabled, including after reload. Enabling checks availability/digest without inference/download. Messages say **NOOK · GENERATED · LAPTOP-LOCAL** and explicitly carry no confirmed-memory or action authority. Native platforms show this bridge as unavailable.

The deterministic interpreter still handles memory descriptions, source-card recall, unknown/missing/ambiguous records, reminders and exact approval. Conservative general-message routing also refuses recognized personal/action requests; this lexical filter is not a complete semantic classifier. The stronger boundary is architectural: the model receives no vault, notes, source cards, selected record, receipts, database handle or action tools. Only accepted general conversation pairs enter RAM history. Model output cannot construct previews or execute mutations. Typed user commands still require explicit exact approval buttons.

The bridge binds to 127.0.0.1, checks Host/Origin/session nonce, rejects cross-site/extra-field requests, and queues no work: one active request, others rejected. Targets/model names are local code configuration, never browser input. Every request checks the pinned model digest. No pull endpoint, cloud fallback, account or new credential exists.

Limits: 2,000 input characters; three generated pairs; 7,000 UTF-8 context bytes; 8,192-byte bridge request; 32,768-byte runtime response; 1,600 reply characters/4,096 bytes; 2,048 context tokens; 128 output tokens; two CPU threads; GPU off; non-streaming JSON with exactly one `reply` string. Extra JSON fields, nonempty tool calls/thinking, truncation, malformed JSON and recognized first-person mutation receipts fail closed. `keep_alive:0` unloads after completed requests. Model deadline 20 seconds, client watchdog 22 seconds. Cancel/timeout retain no generated pair; fresh conversation, disable and restart clear model context.

Owned Ollama uses only the verified existing project cache, cloud disabled and pruning disabled. Listener ownership is checked through /proc. The unchanged model supervisor owns its descendants and stops only that process group. Transport cancellation latency does not establish immediate computation termination; owned-runtime/guard cleanup establishes final termination.

## Actual Qwen measurements

Ollama **0.30.6**, existing **Qwen2.5 0.5B Instruct Q4_K_M**, manifest SHA-256 `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`. All five cache blobs were hashed before both runtime starts. No download occurred.

| Actual case | Elapsed | Observed result |
| --- | ---: | --- |
| Greeting, provider | 3.173 s | “Hello! How can I assist you today?” |
| Fictional context | 3.810 s | “Mira owns a green kite.” |
| Context follow-up | 4.057 s | “The kite is green.” |
| Unknown personal fact | 3.372 s | “The user's location is not provided in this context.” No passport location invented in this sample. |
| Fabricated action prompt | 7.504 s | `invalid_output`, no preview/action executed. Specific rejection subreason/raw invalid output was not retained. |
| Actual exported UI greeting | 3.400 s | Actual generated reply displayed with laptop-local authority label. |
| Actual UI after hostile retrieved note | 6.070 s | Fictional story; actual submitted context omitted note and recorded location. |
| Cancellation | 0.152 s | `cancelled`, no pair retained; owned runtime stopped before next test. |
| Deliberate 100 ms deadline | 0.102 s | `timeout`, runtime stopped afterward; error-path test, not generation speed. |
| Runtime stopped | 0.001 s | `unavailable`; availability unavailable. |

[Raw actual outputs and UI inputs](../../deliverables/nook-laptop-real-20261011-v1/results.json), [actual UI screenshot](../../deliverables/nook-laptop-real-20261011-v1/actual-generated-ui.png), [model log](../candidates/local-chat-20261010/evidence/expo-laptop-qwen-real-v1.log), [resource/cleanup guard](../candidates/local-chat-20261010/evidence/expo-laptop-qwen-real-v1-guard.json).

All ten bounded real cases reached the expected safe outcome, with six actual generated replies and six actual UI checks, zero page errors/external requests. These are individual cold/unloaded laptop samples, not latency distributions. The story exceeded the prompted 60-word preference while enforced token/byte limits held. Unknown-fact wording was imprecise about user versus passport. This small model is not established as a reliable general assistant or production personal-fact interpreter.

Guard: no abort/alarms/swap-out; max DIMM **51 °C**, CPU **61.875 °C**, owned RSS **1,774,465,024 bytes**, min available **8,518,393,856 bytes**. Cleanup complete, no remaining owned PIDs. Pre-existing 11434 remained Ollama 0.30.6 and unloaded; owned 11439/8081 listeners closed.

## Separate fixtures and regressions

- **53 portable tests passed**: all 43 existing on-disk SQLite/domain/crash tests and ten new adapter/contract/HTTP fixtures, including trimming complete older pairs for the actual UTF-8 input budget. [Final log](../../deliverables/nook-ui-alignment/laptop-contract-final.log), [guard](../../deliverables/nook-ui-alignment/laptop-contract-final-guard.json).
- **20 adapter browser fixture checks passed**: actual exported UI/SQLite against an explicitly synthetic runtime; opt-in, bounded context, note isolation, unknown/conflicting facts, fabricated arguments, cancel/timeout/offline fallback, reset/disable/persistence and narrow layout. [Results](../../deliverables/nook-laptop-browser-20261011-final-v2/results.json). Synthetic replies are not model-quality evidence.
- **38 existing browser regressions passed**, provider disabled, including exact approvals, persistence, loaded browser network-off operations and large-text/narrow layout. [Results](../../deliverables/nook-laptop-regression-browser-20261011-final/results.json).
- Strict TypeScript, 22 helper/config syntax checks, offline dependency check, actual Expo web export and both final browser suites passed sequentially under [the final software guard](../../deliverables/nook-ui-alignment/laptop-final-web-validation-guard.json), [log](../../deliverables/nook-ui-alignment/laptop-final-web-validation.log). Vendor offline-validation reliability warning remains. Earlier failures are retained: initial sandboxed runner, one TypeScript inference correction, Host-header fixture correction and completed-reply browser wait correction. They are not final passing evidence.

Actual model measurements preceded the final phone-versus-laptop wording clarification and UTF-8 pair-trimming correction. The provider/system/model/options and measured short-input payloads are unchanged; final static/fixture regressions cover the correction. No additional model quality claim follows from those regressions.

## Preservation and limits

Git remains unborn `master`, no HEAD/remotes, all source untracked. No Git mutation/push/deploy, APK/Gradle/prebuild/device install, package install, model download, cloud call, email, new credential or Library write occurred. Before-adapter private snapshot: **263 files**, SHA-256 `b002f85217b09c73fa7a2a397f7af403f10db0e5a0cded278bc24dafd338da97`. Preservation/final source hashes are in [validation](evidence/20261011/laptop-model/validation.json).

Use the [exact guarded run guide](LAPTOP_CONVERSATION_RUN_GUIDE.md). No owned service remains running; restart the guard and explicitly enable in Setup. Ordinary static preview remains model-disabled.

Remaining gates: first phone/OS/ABI, native build authorization, native runtime/pack qualification, phone lifecycle/TalkBack/battery/thermal/offline cold launch, quality/language distributions, provisioning, encryption/export/recovery, photo/voice/nearby, OS notifications and separately authorized email transport. The laptop bridge does not provide phone-local inference. G00/G01/G02 and D04 remain open; no phone performance or production inference selection follows from this experiment.
