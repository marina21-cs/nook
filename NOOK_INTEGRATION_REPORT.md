> Historical baseline document. Its counts, UI steps and provisioning instructions do not describe the expanded release. See [current release and reproduction notes](docs/EXPANDED_RELEASE.md).

> Historical baseline report. The README and publication provenance state current publication status; this report does not qualify the expanded working candidate.

# Nook final UI integration

The approved Nook mobile UI is connected to the real local backend and verified. The user's explicit approval superseded the prior UI handoff wait. No layout, palette, mascot, animation or application identifier was replaced. No new dependencies, model downloads, external agents, publication or submission occurred.

## Changes

The design already implemented real API wiring. This integration fixed the missing visible **Stop request** control during microphone permission acquisition, recording and transcription, and hides it again when the work ends. The current browser suite now follows the new onboarding, native confirmation dialogs, settings-based speech control and two-step save review. The previous browser command delegates to the current suite. The actual speech harness also follows this design.

Onboarding completion, appearance and reduced-motion preferences persist locally. Questions/transcripts do not. Photo and manual memories require reviewed explicit confirmation. Saved records expose date/source, history and unknown current location; edits, aliases and deletion use real revision/idempotency contracts. Lost responses preserve the exact request for retry. Provider errors retain editable text and switch back to typed recall. No production model result or button action is mocked.

## Verification

- **335 backend tests passed** in 14.02s; 15 real vision cases excluded. One existing Starlette/httpx deprecation warning remains. The first network-restricted sandbox run stalled and was stopped; it is not counted. The successful run used temporary stores with local process networking permitted.
- The sanitized extracted source also passed **335 tests in 16.40s** using the existing Python environment; no installs or model runs. Final documentation-only export updates retain identical executable source hashes.
- **54 browser checks passed** against this Nook UI and a real isolated FastAPI/SQLite service, including service restart/session renewal, actual persistence, manual/photo save→recall→unknown, duplicate/ambiguous items, aliases, malformed images, literal untrusted labels, historical photos, lost commit/delete responses, cancellation, late permission, draft discard and outage retry.
- Speech endpoints/devices are explicitly mocked only in this software browser suite; these checks do not establish real inference or human acceptance. No hardware microphone/camera permission was granted. A canvas stream exercises camera lifecycle.
- Ruff passed; **73 files** formatted; mypy passed **29 app files**; JavaScript syntax and canonical 16kHz PCM16 WAV checks passed.
- Desktop 1280px and mobile 390/320px screenshots inspected. Nook branding, keyboard focus and no horizontal overflow verified. Screenshots show invented fixture records only. Not screen-reader/native-phone acceptance.
- Browser observed zero external requests; this is browser-context scope, not OS-wide isolation.

Evidence: `deliverables/nook-integration/browser-results.json`, `browser-tests.log`, `backend-tests.log`, screenshots and source hashes. Tests clean their own temporary stores and stop their own browser/server processes. The existing design preview is not an owned test process and was not closed.

## Release matrix

| State | Scope |
| --- | --- |
| Implemented and verified | Final Nook UI; onboarding/preferences; deterministic manual/photo memory, dated recall, ambiguity/unknown, edit/history/delete; provider-independent contracts; browser media lifecycle and error/retry wiring |
| Implemented, not accepted with real providers on this UI | Whisper/Kokoro opt-in flow and reviewed speech playback |
| Blocked | Fresh real voice guard stopped before model launch: DIMM **55°C**, high-temperature alarm; min available RAM **5,592,961,024 bytes**; no model worker launched. See `voice/evidence/nook-integration-voice-gate-guard.json`. Guards unchanged. |
| Unverified | Human English/Taglish recognition and listening quality, actual camera/phone/browser/device behavior, native 4GB phone performance, general visual retrieval accuracy |
| Outside this integration scope | New features/providers, model downloads, cloud services, public repository/social publication/deployment/submission |

Prior real evidence remains separate: synthetic backend STT→explicit edit→TTS chain 15.83s; prior browser STT 9.298s followed by guard-interrupted TTS. No current full browser AI pass, unchanged natural spoken-question pass, or manufacturer-safe thermal claim. Typed mode remains useful without models; that is a material limitation for the 25% Local AI rubric and must not be disguised. No score is guaranteed.

## Launch

From the canonical project, use:

```sh
APP_DATA_DIR="$PWD/.demo-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=0 APP_TEXT_MODEL='' .venv/bin/python -m app
```

Open **http://127.0.0.1:8765/**. Get Started → Remember → choose a photo or manual entry → Review memory → check confirmation → Save memory → Chat → type the saved name/question → Send question. Saved → Review record supports correction/history/unknown/delete. Ctrl+C stops the service. `DEMO_RUNBOOK.md` contains opt-in guarded voice instructions; current thermal evidence means use typed mode until existing gates permit speech.

A sanitized source ZIP and verification record are prepared after source stability. It excludes personal databases, secrets, runtime environments and model weights; dependency/provenance/reproduction instructions are included. A source ZIP is not an official hackathon submission. Public publication status is tracked separately in the README.
