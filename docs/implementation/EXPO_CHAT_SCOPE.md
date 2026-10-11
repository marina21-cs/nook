# Nook Expo conversation milestone — 11 October 2026

The user redirected the next milestone: establish and test the Expo experience before building an APK. Nook should feel like an interactive personal assistant, remember user-observed surroundings, and manage reminders when connectivity is unreliable. This scope addendum supersedes the previous build-first work order. The editable Library PRD remains version 1 and is preserved; this addendum records the newer instruction without claiming a Library revision.

## Current slice and authority

Expo/React Native remains the selected production UI. Build a chat-first screen with bounded session history, contextual follow-ups, confirmed source cards, exact memory/reminder previews, and capability/setup states. The interpreter is a narrow deterministic prototype, visibly labeled. It is not Grok, a generative model or a local inference integration.

Confirmed memories are authoritative SQLite records. Chat history, draft text and generated suggestions are not confirmed memories. Retain the PRD AI-02 default: the conversation stays in this JS session and is cleared on restart or a fresh-conversation action. Keep at most 40 messages. Save only after the exact preview button; conversational “yes” and “save that” do not authorize mutations. Pending previews expire after five minutes and are discarded on restart. Committed receipts survive and exact retries cannot duplicate the mutation.

Memory intake now supports narrow natural descriptions and an editable manual fallback. Source is the user's typed description; show observation and save time separately. Use “last recorded,” never live location. Missing, unknown and ambiguous records remain distinct. A selected record ID scopes follow-ups; ambiguity clears implicit context. Store no seed records. Original memory schema/receipt behavior stays unchanged.

Reminders have their own additive, versioned SQLite extension. Review title, resolved date/time with timezone, channel and scope before saving. A local request is `stored_not_scheduled`: due state is visible while Nook is open, with no OS notification promise. Email is `queued_email`: no account, recipient or transport exists; never write a sent state or sent receipt. Review cancellation separately, bind its target/revision, deduplicate identical requests and ensure replay cannot resurrect a cancelled request. Recipient/account selection and separate send review are future requirements, even for a previously approved local queue request.

## Surroundings, offline setup and capability gates

Descriptions are available now. Intentional user-shared photos or camera sessions are the next capture path, subject to explicit permission, normalization/metadata removal and reviewed captions. Nook does not watch or listen in the background and does not know unrecorded surroundings. Photo/voice buttons must not pretend to capture when their adapters are absent. General vision and speech accuracy require their own device/quality qualification.

No manual model copying or weight links are planned for users. App-managed first-run provisioning must present an exact compatible pack, source/license/version/hash, download size, installed size, peak free-space requirement and offline capabilities before consent. Pack selection/size/storage are presently unknown, not invented. Implement these states when a qualified adapter exists: unavailable → awaiting consent → checking storage → downloading with byte progress → paused/retrying or cancelled → verifying → staged activation → runtime/offline-readiness check → ready. Verify bytes before activation, journal transitions, preserve the last usable pack, resume only verified ranges, use bounded retry/backoff and recover interruption/full disk without claiming readiness. Separate consent from cloud processing and optional nearby data. No model download or simulated progress occurs in this milestone.

Nearby information requires an initial permitted network retrieval of a selected area. Later results must show source, coverage, attribution and freshness. Offline cached information is not current opening-hours or live-position evidence. No pack/provider is selected now.

Actual native offline inference is deferred to a development-build/device gate. Expo Go can exercise its supported libraries; it cannot supply arbitrary added llama.cpp/LiteRT-LM native adapters. No native compilation, APK, Gradle, prebuild, device installation, permission change, email connection/send or credential work is authorized for this milestone.

## PRD and phase mapping

| Requirements | This milestone | Remaining qualification |
| --- | --- | --- |
| MEM-01/02, ACT-01/03 | Confirmed typed records, source IDs/dates, preview/approval and read-only recall | Full identity/history/edit/delete corpus; Android lifecycle |
| AI-01/02 | Explicit prototype boundary, session context/privacy, selected-record follow-ups | Real model grounding/quality/cancellation; retained-history export/deletion policy |
| ACT-01, T02/T04 | Reminder draft, exact create/cancel, receipts and crash/replay | OS notification schedule/reboot/timezone handling; separately approved email transport |
| CAP-01/02, T03/T05 | Honest unavailable sensor states and typed fallback | Intentional photo pipeline, permissions, speech/vision evaluation |
| DEV-01, T04 | In-app provisioning contract and unavailable/readiness labels | Qualified packs, hashes/license/storage/progress/recovery/runtime checks |
| PLC-01, T10 | No-pack state and freshness/consent contract | Licensed source, selected region, real retrieval/cache and attribution |
| UX, T05 | Accessible labels, touch targets, plain status/error/source text | Physical TalkBack, large text, keyboard and lifecycle tests |

Portable phase-02 UI/domain work proceeds under the user's instruction while G00/G01/G02 remain open. This does not waive their release requirements or turn browser/Node tests into phone evidence. The original hackathon app and earlier build failures/checkpoints remain preserved. Refer to the [current receipt](EXPO_CHAT_RECEIPT.md) for actual checks and limitations.

## Testing path

Run strict TypeScript and the full mobile portable corpus against real on-disk Node SQLite, including actual child-process exits before/after reminder and memory commit. Export web JavaScript only and exercise the real React Native Web UI with Expo SQLite's WASM worker, isolated-origin headers and browser persistence. Web support is alpha and lacks the native exclusive-transaction API; a web-only serialized connection handles all operations and real BEGIN/COMMIT. Native SQLite code is unchanged. Browser runtime persistence is separate from phone lifecycle and web offline cold reload; no service worker is promised.

Official references: [Expo web](https://docs.expo.dev/workflow/web/), [Expo SQLite web setup and transaction limits](https://docs.expo.dev/versions/latest/sdk/sqlite/), [development builds](https://docs.expo.dev/develop/development-builds/introduction/).
