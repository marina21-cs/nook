## Final Nook UI integration — 9 October 2026, 19:36 UTC

The user approved the finalized UI and explicitly authorized backend wiring. The former UI handoff hold is released by that instruction; no specially named handoff file is required. The authoritative coral opening, mascot, chat and mobile design are preserved. **335 backend tests and 54 browser checks pass on this Nook source**, plus Ruff/formatting, mypy and WAV/JavaScript checks. See [NOOK_INTEGRATION_REPORT.md](NOOK_INTEGRATION_REPORT.md) for scope and evidence. Real speech was not rerun: the fresh guard blocked before launching a model at DIMM 55°C with a high-temperature alarm. No guard was relaxed. Earlier tests/results below remain historical.

# Current mobile interface: Nook

The 10 October mobile redesign adds the reference-video opening, a simple chat composer, reviewed photo/manual saves and mobile record sheets. Use **Send question** in chat and **Review memory → Save memory** in Remember. Current isolated preview and verification: [MOBILE_UI_REPORT.md](MOBILE_UI_REPORT.md). Existing guarded voice instructions below still apply.

# Nook — hackathon v1 launch and stop

Scope and acceptance: `V1_RELEASE_CHECKLIST.md`. Three-minute presentation: `V1_DEMO_SCRIPT.md`. Typed mode is the dependable release demo; real speech is opt-in and subject to the retained guard. The final v1 real transcription passed, while its TTS request was guard-stopped for combined swap activity. Do not describe the default typed run or mocked browser tests as a full AI pass. If the monitor stops the voice server, restart the lightweight command below against the same `.demo-data`, then inspect Saved before retrying a write.

# Run the local interface

The current demo is a mobile-first browser interface served by the existing FastAPI process: Talk, Capture and Saved. The final product name is **Nook**; technical identifiers and paths remain unchanged. This is a laptop-local application, not native phone execution.

## Lightweight mode — no model inference

From the canonical project directory:

```sh
cd .
APP_DATA_DIR="$PWD/.demo-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=0 APP_TEXT_MODEL='' .venv/bin/python -m app
```

Open **http://127.0.0.1:8765/** on this computer. Keep that terminal open; Ctrl+C stops the server. `.demo-data` is a separate persistent demo store; use an empty directory if you want isolated records. This command performs no model inference or downloads. Do not expose the loopback service through a public tunnel.

1. Capture: choose a photo, name one item, enter its recorded place and check the explicit review confirmation. Save once. Importing a photo alone does not save an item. Leaving the screen discards an unfinished draft; reloading cleans up its saved draft identifier.
2. Talk: type the saved name or a question using it, then Confirm & ask. A moved/unknown record is shown separately from a missing item. Multiple matches remain separate records for review.
3. Saved: review source/date and uncertainty. Open a record to update the place, mark it moved/unknown, inspect historical evidence or explicitly delete it. Shared photos remain attached to other records.
4. An uncertain save keeps its exact retry payload in memory. Retry the same details before navigating. If you reload after an uncertain result, inspect Saved before creating another memory.

The default command leaves real speech off. The implemented speech interface includes explicit recording, a 10-second cap, editable transcription, a separate confirmation and manual playback of returned speech. Its browser tests use mocked speech transport and generated device fixtures; they do not establish human speech accuracy. Actual microphone/camera permission is the user's choice in their browser. Camera access starts only with Open camera and stops after choosing one frame, closing, leaving or hiding the tab.

## Opt-in real local AI — Whisper tiny + Kokoro

This mode enables actual local speech models: OpenAI Whisper tiny for transcription and hexgrad Kokoro-82M with `af_heart` for English speech. Recall/tool execution remains deterministic. General visual conversation is not enabled or accepted; the existing detector stays disabled in this speech demo. These are separate product gates, not interchangeable AI capabilities.

Run from the canonical project directory. Use only the existing cached runtime/weights and keep resource supervision active. No installer or network download is part of startup. The exact command is:

```sh
cd .
APP_DATA_DIR="$PWD/.demo-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=1 APP_VOICE_TEST_GUARD_54=0 APP_TEXT_MODEL='' .venv/bin/python scripts/voice_guard.py --stage ui-voice-demo-1 --timeout 180 -- .venv/bin/python -m app
```

Open **http://127.0.0.1:8765/** on the same computer. The guard stops the whole owned process group after at most 180 seconds or on a resource violation. Ctrl+C stops the demo early. Use a fresh stage name after each invocation; existing evidence names are deliberately rejected. Do not run a second server or model worker alongside it.

The app launches one Uvicorn worker bound to `127.0.0.1`. `LocalVoice` serializes STT/TTS through one shared lazy CPU process with two Torch/OMP/MKL/OpenBLAS threads, a 30-second call timeout, offline environment flags and process-scoped network denial. No account, cloud speech API or credentials are needed. A ready API and `artifacts_present=true` mean files are present; only a successful inference request proves model execution.

Paths resolved from the project (not the shell's global Python):

- API/monitor: `./.venv/bin/python`
- Speech worker runtime: `./voice/runtime/bin/python`
- Whisper: `voice/artifacts/whisper/model.safetensors`, official `openai/whisper-tiny` revision `169d4a4341b33bc18d8881c4b69c2e104e1cc0af`.
- Kokoro: `voice/artifacts/kokoro/kokoro-v1_0.pth` and `af_heart.pt`, official `hexgrad/Kokoro-82M` revision `f3ff3571791e39611d31c381e3a41a3af07b4987`.
- `voice/artifacts/manifest.json` pins sizes and SHA256 hashes; the worker validates them before inference. Absence or mismatch fails closed.

The outer monitor retains DIMM <54°C, CPU <75°C, available RAM >=2 GiB, process-tree RSS <5 GiB and the existing CPU/swap/sensor gates. `APP_VOICE_TEST_GUARD_54=0` explicitly retains the worker's stricter **DIMM <52°C** gate; this command does not raise a limit. Three consecutive positive swap-out samples stop the experiment even when temperature and RAM limits pass. These are conservative experimental controls, not manufacturer operating specifications.

### Actual frontend/model check, 9 October 2026

A temporary-data server using this same `python -m app` entry point, port 8765 and real-model settings started in 1.095s and enabled the browser speech controls. One browser-generated canonical WAV from the existing synthetic Kokoro memory-description fixture was transcribed by real Whisper tiny in 9.747s. The editable transcript was shown, no recall was automatically submitted and memory stayed unchanged. The scripted operator then explicitly edited the descriptive transcript to `blue keys` and clicked Confirm & ask with speech enabled.

The real TTS request began, but the monitor stopped the process group after three consecutive positive swap-out samples. **That frontend spoken-reply step is incomplete, not passed.** No inference retry or guard relaxation was performed. Maximum sampled DIMM was 50.5°C, CPU 60.25°C, process-tree RSS 2.47 GiB, minimum available RAM 5.52 GiB, and swap-out 1.43 MiB/s. Server and worker were subsequently confirmed absent and port 8765 closed.

Evidence: `voice/evidence/frontend-real-voice-1.json`, `frontend-real-voice-1-guard.json`, `frontend-real-voice-1-resources.jsonl`, `frontend-real-voice-1-server.log` and `frontend-real-voice-1-cleanup.json`. Device acquisition was a cached PCM fixture; neither microphone nor camera permission was requested. The speech endpoints and model outputs were real. This is a synthetic description with explicit scripted review/edit, not human question accuracy or listening acceptance. The earlier completed backend-only real STT/TTS chain remains separate evidence (`integrated-chain-1.json`, 15.83s known chain). Human English questions, Taglish, human listening and a completed real browser speech round trip remain open.

After a future eligible resource window, the single bounded fixture check can be deliberately run with a fresh name; do not retry it merely to obtain a pass:

```sh
.venv/bin/python scripts/voice_guard.py --stage ui-real-speech-check-2 --timeout 150 -- ~/.nvm/versions/node/v22.22.2/bin/node scripts/frontend_real_voice_test.cjs ui-real-speech-check-2
```

The fixture harness owns a fresh temporary data directory and the port-8765 server, verifies its own bind before requests, and stops its processes. It does not alter `.demo-data` or personal records.

Reproduce software browser checks with the cached browser (no download):

```sh
.venv/bin/python scripts/voice_guard.py --stage ui-browser-demo-1 --timeout 150 -- ~/.nvm/versions/node/v22.22.2/bin/node scripts/frontend_browser_test.cjs
~/.nvm/versions/node/v22.22.2/bin/node scripts/frontend_audio_test.cjs
```

Browser tests own and stop their port-8766 server, use temporary data and never grant actual device permissions. Use a fresh stage name for each run. The fixture output folder is `deliverables/frontend`; original photo attribution is included there. Earlier backend and integrated-voice run instructions are preserved in `deliverables/frontend/demo-runbook-before-ui.md`, and prior limitations remain in `VOICE_IMPLEMENTATION_REPORT.md`.
