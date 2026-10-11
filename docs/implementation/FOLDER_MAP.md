# Nook source and implementation folder map

Existing paths below are verified behavior references. The bounded mobile/expo project now exists with domain, storage, UI, tests and config plugin sources; other proposed destinations remain planning labels. D03 adopts Expo with React Native. SDK dependencies are pinned, while native build/bridge qualification remains D14; use [Expo architecture](EXPO_ARCHITECTURE.md) for native module and generated-project boundaries.

## Existing folders

| Existing folder or file | Reusable work | Replacement or extension needed | Owning phase |
| --- | --- | --- | --- |
| [app/contracts.py](../../app/contracts.py), [app/turn_contracts.py](../../app/turn_contracts.py) | Validation, IDs, unknowns, reviewed rows, revision constraints | Mobile domain types and versioned operation payloads | 01, 02 |
| [app/migrations](../../app/migrations), [app/database.py](../../app/database.py), [app/item_repository.py](../../app/item_repository.py) | Item/observation schema, transaction and receipt semantics | Phone database, local sequence, durable pending operations, mobile migrations | 01, 02 |
| [app/recall_service.py](../../app/recall_service.py), [app/freshness.py](../../app/freshness.py), [app/language.py](../../app/language.py) | Deterministic matching and evidence/freshness semantics | Equivalent corpus on device, indexed retrieval and bounded generation citations | 01, 02 |
| [app/actions.py](../../app/actions.py), [app/requests.py](../../app/requests.py) | Exact previews, cancellation, bounded actions | Durable approval and execution journal across process death | 01, 02 |
| [app/evidence_store.py](../../app/evidence_store.py), [app/capture_service.py](../../app/capture_service.py) | Sanitization, drafts, shared photos, failure handling | Mobile media finalization and lifecycle recovery | 02 |
| [app/static](../../app/static), [PRODUCT.md](../../PRODUCT.md), [DESIGN.md](../../DESIGN.md) | Branding, flows, text, assets and browser behavior | Expo screens and equivalent behavior; native permission/lifecycle/accessibility qualification | 01, 02 |
| [app/local_chat.py](../../app/local_chat.py), [app/chat_context.py](../../app/chat_context.py), [app/conversation.py](../../app/conversation.py) | Bounded context, output validation, read/generation separation | Native runtime adapters and explicit capability routing | 01, 02 |
| [app/local_voice.py](../../app/local_voice.py), [app/audio_service.py](../../app/audio_service.py), [voice](../../voice) | Transcript review, capability/error contracts, provenance | Device/locale speech adapters and measured voice quality | 01 experiment, 02 selected feature |
| [app/inference](../../app/inference), [models/README.md](../../models/README.md) | Model provenance, validated suggestions, manual fallback | Native runtime/artifact lifecycle; separate OCR/vision qualification | 01, 02, 06 |
| [app/poi.py](../../app/poi.py), [app/poi_download.py](../../app/poi_download.py), [app/poi_contracts.py](../../app/poi_contracts.py) | Cache metadata, source labels, explicit area consent | Permitted pack service/download manager, offline index | 02 selected feature, 06 |
| [app/security.py](../../app/security.py), [app/main.py](../../app/main.py), [app/api.py](../../app/api.py) | Local trust-boundary and error examples | Native app-private access; separate cloud authentication and object authorization | 02, 03–05 |
| [tests](../../tests), [scripts](../../scripts) | Behavioral corpus, fault fixtures, laptop verification tools | Mobile unit/instrumentation/device harnesses; baseline repairs | 00–06 |
| [release/github-nook](../../release/github-nook), [submission](../../submission) | Preserved historical source and publication evidence | Read-only provenance inputs; separate reviewed future release artifact | 00 |

## Proposed implementation destinations

| Proposed path label | Intended responsibility | Phase and condition |
| --- | --- | --- |
| `mobile/expo/` | Adopted Expo/React Native app; first feasibility flow, package lock, app configuration and development client | 01 after G00; exact versions under D14 |
| `mobile/expo/modules/nook-ai/` with `android/`, `ios/`, `cpp/` and `src/` as appropriate | Native capability/generation/cancel/release bridge; separate llama.cpp and LiteRT-LM adapters; Android Kotlin/JNI/C++ and later iOS Swift/C++ | 01 Android qualification; iOS only in 06. Bridge packaging must be verified |
| `mobile/expo/plugins/` | Config plugins for reproducible native dependencies, manifests, permissions and backup rules | 01 onward; no secrets |
| `mobile/expo/android/` and `mobile/expo/ios/` | Generated native build projects under the proposed CNG policy; durable custom code lives in modules/plugins | Android 01; iOS 06. Do not edit these as the only source of native behavior |
| `mobile/expo/src/domain/` | Model-independent records, observations, validation and operation types | 01 synthetic slice; 02 durable alpha |
| `mobile/expo/src/storage/` and `media/` | Phone DB, evidence journal and storage recovery | 02 |
| `mobile/expo/src/approvals/` | Payload binding, expected revisions, approval/execution state, receipts | 02 |
| `mobile/expo/src/retrieval/` and `ai/` | Confirmed-source lookup, bounded generation and capability routing | 02 |
| `mobile/expo/src/migration/` | Versioned snapshot export, dry-run/import and activation journal | 02 |
| `mobile/expo/src/speech/` and `places/` | Separately qualified voice and selected-region caches | 02 if selected |
| `mobile/expo/src/cloud-consent/` and `services/ai-proxy/` | Selected-payload consent and bounded server inference | 03 |
| `mobile/expo/src/vault-backup/`, `services/account/`, `services/vault-storage/` | Client encryption, recovery and optional authorized ciphertext storage | 04 |
| `mobile/expo/src/device-sync/` and `services/sync/` | Approved operation outbox, causal merge, media protocol and revocation | 05 |
| `mobile/expo/src/household/`, `mobile/expo/src/vision/` and platform modules | Selected expansion, shared Expo UI plus separately qualified native adapters | 06 |
| `tests/native/`, `tests/cloud/`, `tests/backup/`, `tests/sync/` | Portable corpus and meaningful acceptance harnesses | As corresponding phase begins |
| `evidence/native/<build>/<device>/` | Private raw traces, fixture manifests and summarized measured results | 01 onward; content-free measurements where possible |

Existing Python source remains a reference until a separately reviewed change is authorized. Do not copy the entire working tree into a release: it contains private data locations, model/runtime assets, and historical snapshots. No new source path above is a promise that the existing source will be moved or deleted.
