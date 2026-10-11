# Current implementation note — 2026-10-09

The typed/manual portion of bounded turns is now implemented at `POST /api/turns`; frame/utterance are ephemeral, no implicit save. Replaceable speech protocols default unavailable and audio input remains rejected until providers/artifacts are selected and accepted. Real call audio/STT/TTS remain pending. See [API](API.md) and [phase report](../BACKEND_PHASE_REPORT.md). The proposal below is preserved historical design, not current endpoint syntax.

---

# Next backend phase: bounded spoken visual turns

User direction: tap to open an in-app call-style assistant, intentionally show one household object, ask aloud and hear a response. **This phase is planned, not implemented.** No voice package, hosted voice request, credential, frontend, audio recording or streaming endpoint was added to the completed visual-memory backend. ElevenLabs/provider/project licensing is being verified separately; no particular GitHub project has been selected.

## Proposed turn boundary

One user turn consists of one explicitly initiated speech capture (or typed transcript alternative), one intentionally chosen still frame, local category analysis, a structured response grounded in current evidence/confirmed memory, and optional speech rendering. Stop/cancel discards late output. No continuous camera loop, background microphone, live tracking, automatic inventory or unbounded agent/tool loop.

Call audio/frame/transcript should be **ephemeral by default**, with no SQLite item, observation or durable photo write. Use the existing bounded image sanitizer and isolated verified vision adapter without committing capture drafts. Once the response is complete/cancelled, release bytes; operational logs must omit audio/photo/transcript contents. If the user chooses Remember, create a review draft through a separate action and require the existing explicit personal-name/location/identity confirmation. A spoken/model-generated instruction alone must never bypass that confirmation. Existing `/api/captures` are temporary visual-memory drafts with TTL/restart cleanup; they are not yet an ephemeral call-turn endpoint.

## Proposed interfaces and response

Keep `SpeechToText.transcribe(audio, cancellation)` and `TextToSpeech.render(text, cancellation)` behind separate bounded provider interfaces. Prefer a legally verified local offline implementation; default unavailable/manual text response until it is provisioned and tested. A cloud provider would be an explicit opt-in with disclosure/authorization and cannot become a silent dependency of offline vision/recall. Provider output is untrusted data and has no shell, arbitrary files, URLs or mutation authority. Audio format/duration/byte limits, supported language, model/download size and runtime budget await that provider decision.

A future turn endpoint should accept one bounded audio upload **or** transcript plus one optional bounded frame; forbid unknown fields, duplicate keys and model-authored tool destinations. Return a structured result before any speech rendering:

```json
{
  "turn_id": "UUID",
  "kind": "candidate_or_clarify_or_memory_or_unknown",
  "candidates": [],
  "confirmed_memory_matches": [],
  "reply_text": "Grounded text rendered by application code",
  "inference": {"vision_used": true, "identity_verified": false},
  "persisted": false,
  "speech": {"available": false, "status": "not_provisioned"}
}
```

This is a proposed contract, not an existing API. A memory reply must retain last-recorded location/date/photo/revision and stale/unknown/duplicate behavior from `/api/recall`. The current image can support a tentative category response; it cannot establish a personal identity, current location or movement. Category-to-personal-record matching must ask for clarification rather than automatically selecting a similar object. Medical/hazard decisions remain excluded.

## Current capability and missing work

NanoDet is a fixed 80-class detector, **not a vision-language reasoning model**. It misses keys/chargers/wallets/eyeglasses and produced false airplane/giraffe candidates in tests. Qwen2.5 0.5B and Gemma3 1B are text-only, and their tested normalization did not improve retrieval. No component currently supports general visual conversation. The completed backend handles selected photo candidates, explicit memory saves and grounded recall; it has no live speech-to-text, speech output, call session or audio API.

Next implementation gate: select a verified speech-to-text and speech renderer with licenses, download/resource disclosure and cancellation/offline behavior; decide supported questions given detector limits; then add the ephemeral one-turn orchestration and strict response contract. Test fresh audio/frame input, recognition failures, ambiguous objects, unsupported questions, cancelled turns, no default persistence, explicit Remember boundaries, restart, latency and offline/no-external-request behavior. A larger local visual reasoning model would be a separate feasibility/provisioning gate. Frontend/phone camera/microphone/transport/accessibility tests remain a later phase.
