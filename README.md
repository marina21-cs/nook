# Nook

## The project

Nook helps you remember where you last recorded a household item. Save a reviewed memory, then ask for its last-recorded place, timestamp and supporting evidence.

**Features**

- Save item names, places and photos after explicit review.
- Find confirmed memories through typed questions and aliases.
- See dated evidence, with clear missing or ambiguous results.
- Correct records, review history, mark locations unknown and delete memories.
- Keep memories across app restarts.
- Use a responsive interface with light/dark appearance and reduced-motion settings.
- Add optional local dictation and spoken replies with separately provisioned speech models.

**Repository:** https://github.com/marina21-cs/nook  
**Registered team and members:** pending verification.  
**Source version:** the verified baseline at [source commit `fca8ae7`](https://github.com/marina21-cs/nook/tree/fca8ae7d5ca22560550d000c9f01468d2b982052). Later documentation updates leave application, script and test bytes unchanged. [Version evidence](docs/PUBLICATION_PROVENANCE.md) records the original ZIP and hashes.

**Tested hardware:** AMD Ryzen 5 7535HS, 6 cores/12 threads, approximately 14.8 GiB usable RAM, Manjaro Linux x86_64 and CPython 3.11.15. This is a laptop-local browser app; native-phone performance has not been tested.

**Setup — typed mode**

```sh
git clone https://github.com/marina21-cs/nook.git
cd nook
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
APP_DATA_DIR="$PWD/.demo-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=0 APP_TEXT_MODEL='' .venv/bin/python -m app
```

Open http://127.0.0.1:8765/. Choose **Get Started → Remember**, enter an item and place, review and confirm, then ask in **Chat**. Try the [synthetic examples](examples/synthetic-memories.json). Stop with Ctrl+C.

This configuration needs no model, account or cloud AI key. [Reproduction instructions](V1_REPRODUCE.md) cover optional tooling and speech. Dependencies are pinned with hashes in [requirements.lock](requirements.lock). Models, environments and personal databases are excluded from the repository; the application does not download models automatically.

**Why does this product benefit from running AI locally?**

Household memories and spoken questions can be personal. With the optional speech runtime installed, Whisper can transcribe speech and Kokoro can speak a reply on the laptop without sending that audio to a cloud AI provider. This design supports offline voice processing after setup and avoids dependence on a per-request cloud AI service. The testing limits below apply; local execution does not guarantee better speed or accuracy.

Confirmed memories and photos also stay in local storage. That benefit comes from SQLite and application logic, separate from AI. Typed recall uses structured evidence lookup; there is no accepted general conversational model in this release.

## The proof

**Approximately one-minute demo:** pending.  
**X/LinkedIn video URL:** pending.  
**Screenshots:** [six inspected baseline captures](deliverables/nook-integration/README.md), using invented records and a credited public photo. [Screenshot hashes and provenance](docs/SCREENSHOT_PROVENANCE.json).

![Review a memory before saving](deliverables/nook-integration/capture-desktop.png)

![Recall a dated record](deliverables/nook-integration/recall-desktop.png)

**Testing and setup limits**

The release owner recorded **335 backend tests, 54 browser checks and 335 extracted-source tests passed** for this baseline. Fifteen real-vision cases were excluded. Browser speech/device boundaries were mocked; these results establish software behavior, not physical camera/microphone quality. See [browser results](deliverables/nook-integration/browser-results.json) and [archive verification](docs/BASELINE_VERIFICATION.json). No heavy tests or model runs were performed for these documentation updates.

Optional speech has earlier synthetic backend evidence, but full UI speech, human English/Taglish quality and clean-machine voice installation remain unverified. It requires a separate compatible runtime and matching artifacts; laptop-specific resource guards fail closed on unsupported sensors. A later voice preflight stopped on a hardware temperature alarm. General visual recognition and native 4GB-phone performance are also unverified. A photo or saved record does not establish an item's current physical location.

Later actions, profile/setup changes and area downloads are outside this published version and await their own runtime acceptance. The baseline contains an offline POI-import/cache API, but no built-in area downloader, GPS or routing.

```sh
.venv/bin/python -m pytest --ignore=tests/test_vision.py
.venv/bin/ruff check app tests scripts
.venv/bin/mypy app
node scripts/frontend_audio_test.cjs
# Requires separately installed Node, Playwright and Chromium:
node scripts/nook_browser_test.cjs
```

**Local versus internet:** the browser interface, loopback Python API, SQLite records, photos and typed recall run locally. Optional speech also runs locally after provisioning. Initial dependency/model acquisition requires internet or a prepared cache; GitHub and video/social hosting require internet. Any future explicit area refresh requires internet, while its intended cached lookup is ordinary local data access, not AI. No runtime cloud inference API is needed by the setup above. Scoped browser checks saw no external requests; they do not establish OS-wide network isolation.

## The disclosures

**Runtime components**

| Component | Purpose | Configuration in this release |
| --- | --- | --- |
| Structured evidence lookup | Retrieve confirmed records, aliases, dates and photos from SQLite | Default typed flow; deterministic application logic, not a language model |
| [Whisper tiny](https://huggingface.co/openai/whisper-tiny/tree/169d4a4341b33bc18d8881c4b69c2e104e1cc0af) | Local speech-to-text | Optional; off in the setup command |
| [Kokoro-82M / af_heart](https://huggingface.co/hexgrad/Kokoro-82M/tree/f3ff3571791e39611d31c381e3a41a3af07b4987) | Local text-to-speech | Optional; off in the setup command |
| [OpenCV Zoo NanoDet](https://github.com/opencv/opencv_zoo/tree/81a2a35b00f92e9bd03f03d9b611076d9aa2f942/models/object_detection_nanodet) | Object-box/category suggestions when enabled with matching weights | Disabled in the setup command; poor target-item results, so user review remains essential |

Speech file URLs, pinned revisions, sizes and SHA256 hashes are in the [artifact manifest](voice/artifacts/manifest.json); NanoDet's hash and terms are in [model provenance](models/README.md). No weights are published. Retained [voice/model notices](voice/licenses/), [Whisper model card](voice/artifacts/whisper/README.md), [NanoDet license](models/LICENSE) and [dependency provenance](V1_PROVENANCE.md) preserve their separate terms, including GPL/LGPL speech components.

**Experiments, not the core engine:** SmolVLM-500M was benchmark-only and was not integrated; its CPU FP32 test timed out after 30 seconds at about 3.9 GiB peak worker RSS. Pre-existing Qwen2.5 0.5B and Gemma 3 1B were evaluated for bounded search normalization, remain disabled by default and did not establish a retrieval improvement. None is an accepted general conversational engine. [Experiment identities, results and license disclosures](docs/MODEL_EXPERIMENTS.md).

**Frameworks and technologies:** Python, FastAPI, Pydantic, Uvicorn, SQLite, HTML/CSS/JavaScript, Pillow, HTTPX, OpenCV and NumPy. Optional speech uses CPU PyTorch, Transformers, Kokoro, Misaki and spaCy. Tests use pytest, Ruff, mypy and Playwright/Chromium. Exact versions and retained hashes: [base lock](requirements.lock), [speech inventory](voice/evidence/dependencies.json), [speech provenance](release/v1/voice-dependency-provenance.json).

**APIs and cloud services:** local FastAPI; official package/model sources for provisioning; GitHub for code hosting. ElevenLabs is planned for video postproduction narration, separate from Nook's local speech. No completed ElevenLabs generation, cloud runtime inference or deployment is claimed here.

**Existing code and assets:** the NanoDet adapter uses Apache-2.0 OpenCV Zoo reference logic. Tabler icons retain their [MIT notice](docs/mobile-ui-reference/TABLER-LICENSE). The keys photo is Eviatar Bach / InverseHypercube's “Keys with pink background.JPG”, CC0 1.0; see [fixture attribution](tests/fixtures/vision/README.md). The included WAV is synthetic Kokoro speech. The UI uses system fonts and inline vectors; final rights/history confirmation for the Rello-inspired mascot and reference-based visual treatment remains pending. Reference captures are excluded. Existing Python/Ollama runtimes and installed text models predate this implementation.

**AI development tools:** Codex assisted code, tests, design, documentation and publication preparation. Complete contributor, pre-hackathon code and additional AI-tool history still needs team confirmation; exact development-model versions and actual Devin use are not inferred from filenames or sponsor tags.

**Application license:** pending the owner's decision; no blanket code license has been selected. Third-party notices remain applicable. Team details, final media/social URLs and disclosure completeness remain open submission fields.
