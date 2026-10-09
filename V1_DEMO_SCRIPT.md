> Historical baseline document. Its counts, UI steps and provisioning instructions do not describe the expanded release. See [current release and reproduction notes](docs/EXPANDED_RELEASE.md).

# Nook — three-minute hackathon demo

Start the local typed service from `DEMO_RUNBOOK.md` before presenting. Use the included CC0 `tests/fixtures/vision/keys.jpg` and explicitly call it a test photo. Do not use a participant's personal image or request microphone/camera access during a recorded demo.

| Time | Action | Say / fallback |
| --- | --- | --- |
| 0:00–0:20 | Show Talk, Capture and Saved. | “Nook is a local record of where you last put something. It is not live tracking.” |
| 0:20–1:00 | Remember → choose fixture → name `blue keys` → location `Desk drawer` → Review memory → check review box → Save memory. | “The photo is a clue. I confirm the item and place before the app remembers it.” If file upload fails, stop and show existing verified screenshots; do not pretend it saved. |
| 1:00–1:35 | Talk → type `Where are my blue keys?` → Send question. | Read the date, source and “Current location is unverified.” Ask `Where is my passport?` to show honest not-found behavior. |
| 1:35–2:10 | Saved → Review record → update place to `Hall shelf`, then mark moved/unknown. | “A correction adds history. The old photo does not prove the new or current location.” |
| 2:10–2:40 | Explain optional voice using the runbook/results. If a guarded voice process is already safely running and permission was explicitly granted by the user, record one short question, inspect/edit the transcript, confirm, then manually play any returned audio. | “Speech runs locally and every transcript is reviewable.” On unavailable/timeout/guard stop, immediately use typed mode. Do not keep retrying models, relax limits or call a fixture a human accuracy pass. |
| 2:40–3:00 | Show explicit delete confirmation or final checklist. | “You control what is kept. This v1 ships local confirmed memory and recall; human voice quality, general visual recognition and native phone execution still need validation.” |

If the monitored voice process stops the server, start the separate lightweight command and reopen the same `.demo-data` directory. Never run both servers on the same port. Prior confirmed records survive; review Saved before retrying any interrupted write. The cached synthetic voice evidence may be described/shown, but it must not be presented as a live interaction or human speech acceptance.

Stop with Ctrl+C in the owning terminal. The voice guard also enforces its total time budget. Leave no test server running after the demo.

## Judging rubric supplied by the user

| Weight | Category | Evidence to show honestly |
| --- | --- | --- |
| 25% | Problem / usefulness | One concrete lost-item problem; reviewed photo → saved place → dated recall → correction. |
| 25% | Local AI | Identify real Whisper/Kokoro model execution, local artifact paths and measured laptop results. Removing these models removes dictation and spoken replies; typed memory/recall still works, so do not claim the whole core depends on AI. This is a material judging risk. |
| 20% | Technical | Confirmation, provenance/uncertainty, deletion, restart, idempotency/cancellation and exact test evidence against the authoritative UI. |
| 15% | Innovation | Explain the specific combination of user-controlled memory and local reviewable speech. Do not invent novelty or benchmark superiority. |
| 15% | Product / demo | Use the user's finalized mobile design once the active UI task hands it off; show one coherent flow and a truthful failure fallback. |

For Local AI, a typed-only or mocked run is **not evidence of actual model execution**. Actual retained evidence: real frontend transcription of a synthetic description in 9.298s; current TTS attempt guard-stopped; earlier separate real backend STT→explicit edit→TTS chain completed in 15.83s before human review/playback. If showing saved evidence, label it recorded evidence rather than live output. Hardware is the measured laptop, not a phone. Human speech quality/listening remain unverified.

Meaningful local advantages supported by implementation: audio/model execution need no cloud account, runtime model files are local and downloads disabled, input is ephemeral unless separately confirmed as memory, and model calls have explicit time/resource limits. Browser/Python network tests are process-scoped, not OS-wide isolation. Do not claim lower latency than cloud, zero operating cost, a mobile RAM ceiling, or zero hallucination without comparative evidence. The model-free core remains useful but cannot substitute for the 25% Local AI demonstration.

The finalized Nook UI is now integrated and checked; use its actual Chat / Remember / Saved labels. The rubric image is judging guidance. See NOOK_INTEGRATION_REPORT.md for current acceptance and remaining local-AI risk.
