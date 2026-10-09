# Nook — hackathon v1 dependency and model provenance

No packages, models or browsers were downloaded for this release. Runtime and weights are excluded from the source ZIP.

| Component | Pinned evidence | Source / terms |
| --- | --- | --- |
| API/test dependencies | `pyproject.toml`, `requirements.lock` (versions and SHA256 hashes) | Python package sources recorded in lock; tested Python 3.11 |
| Voice dependencies | `voice/evidence/dependencies.json`, `install-input-manifest.json`, `release/v1/voice-dependency-provenance.json` | Exact filenames, sources, versions, licenses and hashes; cached reuse distinguished from newly provisioned prior inputs |
| Whisper tiny | `voice/artifacts/manifest.json` | Official `openai/whisper-tiny`, revision `169d4a4341b33bc18d8881c4b69c2e104e1cc0af`; model card Apache-2.0; upstream Whisper code MIT |
| Kokoro-82M / af_heart | Same artifact manifest; `voice/licenses/kokoro-README.md`, `kokoro-VOICES.md` | Official `hexgrad/Kokoro-82M`, revision `f3ff3571791e39611d31c381e3a41a3af07b4987`; retained model/voice notices |
| Speech runtime versions | Dependency inventory | PyTorch 2.8.0+cpu, Transformers 4.57.1, Kokoro 0.9.4, Misaki 0.9.4, spaCy 3.8.16, English support model 3.8.0 |
| Speech third-party components | `voice/licenses/` | Includes GPL eSpeak/phonemizer and LGPL num2words; no blanket license is inferred for the assembled runtime |
| Optional existing NanoDet | `models/README.md`, `models/LICENSE`, pinned constants in `app/inference/nanodet.py` | Weights excluded; detector is disabled in v1 demo and not general visual acceptance |
| Browser test tools | Existing cached Playwright and Chromium 1234 | Tool binaries excluded; configurable local paths, no installer in test scripts |
| Photo fixture | `tests/fixtures/vision/keys.jpg`, manifest and README | Eviatar Bach / InverseHypercube, “Keys with pink background.JPG”, CC0 1.0; existing verified public fixture, not a user's household photo |
| Speech fixture | `voice/evidence/kokoro-readback-16k.wav` | Previously generated synthetic memory description; SHA256 `76da9b0d60504ee41e7c1aa00cbeb0756ec6885961dce94075e2b63021b087d2`; not a human recording |

The package retains source/model metadata and license notices, not a grant to redistribute all excluded dependencies. No blanket project license is added. Model outputs, labels and timestamps in test fixtures are synthetic/test data. Actual household records, transcripts, private recordings, model weights and credential stores are absent from the archive.

The release dependency inventory adds retained cached-wheel hashes and installed distribution metadata/RECORD hashes. Where an original wheel URL/hash is not retained, it says so explicitly; a RECORD hash is not claimed to be a wheel hash. Exact binary environment reconstruction is therefore limited to the retained artifacts/approved local environment.
