# Nook PRD reconciliation

The [current Expo PRD](<prd/Nook native application PRD.docx>) is the continuation source. The [original PRD](<../native-readiness-20261011/prd/Nook native application PRD.docx>) is preserved as historical evidence. It establishes proposed native requirements and evaluation gates. This reconciliation connects those requirements to the actual workspace without treating proposals as delivered engineering.

## Direction retained for planning

The user's adopted direction is Android first, with memories authoritative on the device and cloud AI used only after explicit approval. Preserve the hackathon application and uncommitted work. Expo with React Native is the adopted production framework (D03). The planning package was followed by the authorized typed-memory source milestone. The latest instruction pauses all APK/native build work and prioritizes the conversation experience; see the [Expo chat scope addendum](EXPO_CHAT_SCOPE.md). The Library PRD remains version 1; the addendum records the newer work order and reminder/provisioning details.

The following PRD requirements are retained as implementation invariants: confirmed record authority; dated evidence; exact approvals for writes; private local storage; model-independent save/search/edit/delete; capability fallback without upload; and separate consent for cloud AI, backup, sync, and nearby downloads. Their full qualification remains planned. The later authorized typed-memory foundation is recorded in [the milestone receipt](IMPLEMENTATION_RECEIPT.md); it does not close physical-device or optional-service acceptance. The [decision log](DECISIONS.md) identifies choices that remain proposals.

## Repository facts and implications

| PRD topic | Observed current source | Implementation implication |
| --- | --- | --- |
| Published snapshot | Remote main resolved to 1eb0bc7; local Git has no commits/remote | Preserve both identities; do not describe the local folder as a clean checkout at that SHA |
| Local-authoritative records | Python/FastAPI with laptop SQLite and app-owned JPEG files | Port behavior into phone storage/lifecycle; a UI wrapper alone leaves data on the laptop |
| Recall and unknowns | Deterministic names/aliases/tokens; explicit unknown location and dated cards | Reuse corpus and semantics; add full-text ranking only with equivalent ambiguity behavior |
| Approval | Typed payloads, revisions, fingerprinted receipts; proposals live in RAM | Make proposal/receipt transitions durable and bind trusted approval to exact payload, expiry, and scope |
| Conversation | Optional Ollama transport and RAM-only bounded contexts | Implement native adapters; laptop generation evidence does not qualify a phone |
| Photo storage | Normalized evidence, provenance, shared-photo handling, recovery tests | Preserve these semantics; replace POSIX file locks/permissions with reviewed mobile storage operations |
| Nearby | Cached POIs and an explicitly enabled Overpass downloader | Carry over data labels and consent concepts; choose a compliant production source before shipping |
| Speech and vision | Python workers, capability contracts, optional assets | Reuse requirements and evaluation examples; on-device locale/accuracy/resources require fresh evidence |
| Migration | SQL schema upgrades exist; no general vault exporter/importer was identified | Build versioned consistent export and journaled import rather than treating source ZIPs as data backups |
| Cloud/backup/sync | No corresponding production services or native protocols identified | Separate milestones; do not expose the loopback API as the production cloud boundary |

Current app and script bytes match the preserved approved publication snapshot. Historical reports contain multiple versions and superseded acceptance windows. Treat the [readiness ledger](00-readiness/EVIDENCE.md) as the current observation, and attach historical evidence only with its exact source identity.

## Gemini consultation

Section 13 records three rounds on 10 October. Useful themes retained: feasibility first, independent record authority, bounded inference, trusted approval, safe migration, and conflict-preserving sync. Unsupported blanket rejection of shared frameworks, fixed RAM/speed predictions, mmap survival guarantees, outdated runtime descriptions, and English-only speech as a Taglish solution were challenged and excluded.

Gemini's design consultation does not choose Gemini API for Nook. The provider, permitted audience, retention, processing region, and budget remain open. Consultation output supplies no handset benchmark.

## Proposals still requiring evidence or choice

- The user’s 11 October Expo decision supersedes the original thin Kotlin UI experiment and open framework choice. Phase 01 uses an Expo development build with native inference modules; Kotlin/C++ remain possible bridge internals. Expo Go cannot load arbitrary added inference libraries. Local Android compilation and optional EAS are documented in [Expo architecture](EXPO_ARCHITECTURE.md).
- llama.cpp and LiteRT-LM are the first comparison; runtime commits, converted artifacts, quantization, model alternative, and settings remain to be pinned.
- Two different 4 GB phones plus a midrange phone are the PRD qualification matrix. A first named phone can support an initial experiment, not broad 4 GB support.
- Warm first token p95 ≤3 seconds, median decode ≥5 tokens/second, cancellation ≤500 ms, and ≥90% speech intent plus critical entities are proposed thresholds. Record owner-approved thresholds before evaluation; retain failed distributions.
- English, Filipino, and Taglish are evaluation targets. Advertised launch languages require measured quality.
- Provider-blind backup, a recovery secret, same-user sync before household sharing, and list-only place packs are proposed designs with later decision/security gates.
- Price examples in the PRD are dated 10 October research. Reverify official terms and rates before selecting or spending; this package introduces no commercial commitment.

## Phase translation

Folder 00 is the added readiness checkpoint. Folders 01–06 map exactly to PRD phases 0–5. Optional cloud and backup may proceed independently after the local alpha. Sync depends on recoverable key/device ownership from backup. Expansion depends on the capability being selected, with household sharing requiring prior backup and sync gates.

Changes to scope, numerical targets, framework, provider, or supported devices belong in [DECISIONS.md](DECISIONS.md), with a link to the changed requirement and evidence. Preserve the original PRD and update the current editable revision for authorized scope decisions. The [revision record](EXPO_REVISION.md) identifies the approved delta and Library result.
