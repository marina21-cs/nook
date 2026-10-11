# Dependency, model and execution disclosure

Checked 9 October 2026. This is a laptop backend, not a phone build or deployed service. Original source was written for this task with Codex assistance, applying the user-approved Obsidian skills read-only. The reviewed NanoDet preprocessing/postprocessing is adapted from the Apache-2.0 OpenCV Zoo reference, with attribution/license retained; other application code was written for this task. Python/Ollama and installed models predate this implementation.

## Verified environment and installed packages

- Manjaro Linux x86_64; kernel `6.12.77-1-MANJARO`.
- AMD Ryzen 5 7535HS, 6 cores/12 threads. Initial available memory was about 7.7 GiB out of 14.8 GiB usable; about 85 GiB disk space free. This is a snapshot, not runtime memory or GPU evidence.
- Shell default Python 3.14.3; project interpreter is the already-installed CPython 3.11.15 from the user's uv-managed runtime. `.venv` is isolated and does not use system site packages.
- An exploratory isolated CPython 3.11.14 download (29.8 MiB, Astral python-build-standalone vendor release) was made in the delegated task workspace before the existing 3.11.15 was found. It is unused. System Python and the existing interpreter link were not replaced.
- Ollama 0.30.6 at the fixed loopback address. No Ollama settings were changed and no text-model weights downloaded. Local text and NanoDet CPU tests are actual inference; no GPU or phone inference was run.

Direct dependencies were installed from official `https://pypi.org/simple` / PyPI wheel storage. `requirements.lock` pins the complete runtime/test dependency closure and distribution hashes. No system-wide installation, system security/network change, persistent credential, cloud API, container or deployment was created.

| Direct package | Version | Distribution license |
| --- | --- | --- |
| FastAPI | 0.143.0 | MIT |
| Pydantic | 2.14.0 | MIT |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| Pillow | 12.3.0 | MIT-CMU |
| HTTPX | 0.28.1 | BSD-3-Clause |
| opencv-python-headless | 4.13.0.92 | Apache-2.0 OpenCV / MIT packaging; bundled third-party notices retained |
| NumPy | 2.2.6 | BSD-3-Clause plus bundled third-party notices |
| pytest | 9.1.1 | MIT |
| Ruff | 0.16.10 | MIT |
| mypy | 2.4.0 | MIT |

Licenses above come from installed package metadata. Transitive metadata is included in [dependency inventory](dependency-inventory.json). No paid or provider-specific AI SDK is required. The current Starlette TestClient emits a deprecation warning for its HTTPX compatibility shim; tests pass using that supported shim. `httpx2` was not added merely to suppress the warning.

## Existing text models

| Model | Installed digest | Bytes | Quantization | Local license metadata |
| --- | --- | --- | --- | --- |
| `qwen2.5:0.5b` | `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67` | 397,821,319 | Q4_K_M | Apache-2.0 |
| `gemma3:1b` | `8648f39daa8fbf5b18c7b4e6a8fb4990c692751d49917417b8842ca5758e7ffc` | 815,319,791 | Q4_K_M | Gemma Terms of Use, existing installed copy |

Ollama reports completion/tools for the Qwen candidate and completion for Gemma 1B. Neither installed model advertises vision. The official [Gemma 3 1B page](https://ollama.com/library/gemma3:1b) also distinguishes its text input from larger vision variants. Family branding does not establish image support.

The adapter uses Ollama's [schema format interface](https://docs.ollama.com/capabilities/structured-outputs), then checks types, unknown/duplicate fields, intent, term bounds and distinguishing words. One repair is allowed; original-query search is always retained. Both models were evaluated on the same 20 synthetic-record recall queries three times. See [text-evaluation.json](text-evaluation.json). Neither improved retrieval over the deterministic baseline. Text normalization is therefore disabled by default; no semantic-quality or multilingual claim is made.

The first request of each model run includes any actual load incurred; it is not a controlled cold-load benchmark. CPU/GPU allocation, peak runtime RAM, phone inference and representative household usefulness were not measured. Published model sizes are disk bytes, not runtime memory estimates.

## Installed, user-authorized vision alternative

**OpenCV Zoo NanoDet-m-plus-1.5x_416**, `object_detection_nanodet_2022nov.onnx`, replaces the initially proposed MediaPipe route after its licensing/offline gate could not be completed. MediaPipe and EfficientDet were never installed, used or accepted. The user explicitly authorized this small Apache-2.0 alternative and ordinary compatible project-local packages.

- Exact model: **3,800,954 bytes**, SHA256 `4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186`, official revision `81a2a35b00f92e9bd03f03d9b611076d9aa2f942`.
- [Pinned official source](https://huggingface.co/opencv/object_detection_nanodet/resolve/81a2a35b00f92e9bd03f03d9b611076d9aa2f942/object_detection_nanodet_2022nov.onnx), [hash provenance](https://huggingface.co/opencv/object_detection_nanodet/commit/81a2a35b00f92e9bd03f03d9b611076d9aa2f942), [model card/license](https://huggingface.co/opencv/object_detection_nanodet). The model card explicitly licenses all directory files, including weights, under Apache 2.0. Full license retained in `models/LICENSE` and reference directory.
- Exact CPU runtime: `opencv-python-headless==4.13.0.92`, `numpy==2.2.6`, installed in each project-local Python 3.11.15 environment from official PyPI. No other OpenCV flavor or MediaPipe was installed. uv reported downloads of **57.6 MiB OpenCV + 16.0 MiB NumPy**, plus **3.63 MiB weights** (about 77.2 MiB total); installed footprint differs. Distribution hashes are locked. Wheel license/third-party notices remain in their `.dist-info` metadata and must be retained if redistributed.
- Actual implementation: fixed 416×416 RGB letterbox/normalization, six strictly checked ONNX output tensors, stable distribution decoding, class-aware NMS, original-evidence coordinates, candidate cap 20, score threshold 0.35, CPU/OpenCV backend with two threads and OpenCL disabled. No downloaded script is executed; reviewed reference copies are `.py.txt` only.
- Only the approved model hash runs. Operator override requires a local regular file plus matching digest; symlinks/arbitrary weights fail closed. Worker rereads with no-follow semantics, verifies size/hash and loads those exact bytes. Missing or altered files return an honest manual-confirmation error. Startup performs no fetch or inference; readiness and verified inference are separate.
- At most one disposable vision worker, 15-second timeout/cancellation with termination. Workers deny Python socket/DNS calls. Real offline evaluation and HTTP lifecycle completed with outbound Python sockets blocked and zero runtime connection attempts. No cloud, telemetry or runtime asset download was observed in this guarded path; native socket syscalls were not traced and physical WAN/LAN was not disconnected. [Evidence](VISION_RESULTS.md).
- Measured: 20/20 worker captures completed; full worker median **405.10 ms**, p90 **437.85 ms**, first **380.43 ms**; 30 in-process warm inferences across ten cases median **68.44 ms**, p90 **101.62 ms**. Initialization after runtime imports **83.40 ms**; preprocessing varies with photo size. Peak child RSS observed on Linux **336.49 MiB**, including process/runtime/image overhead. Real HTTP `/suggest` was **814.93 ms** in the staged run; see canonical smoke report for its final measured value. These are convenience-photo CPU measurements, not phone/GPU, controlled OS-cache-cold performance, or a promise for every capture.

COCO category detection is limited: keys, chargers, wallets and eyeglasses are unsupported; personal names, distinguishing identity and locations are never inferred facts. The real test photos expose missed spoons, duplicate boxes, false airplane/giraffe labels, and degradation under blur, darkness, rotation and low resolution. Manual correction is essential. The five public-photo sample does not satisfy the plan's 12–20 representative user drawer photos, held-out object fit or measured review-effort improvement. [Fixture provenance](../tests/fixtures/vision/README.md) and [full outputs](vision-evaluation.json).

Default startup uses the verified file in `models/`, outside private SQLite/photo storage. `APP_VISION_DISABLED=1` disables it. The application never downloads packages/models, accepts remote photo/model URLs, or sends private photos to a service. Fresh-checkout provisioning instructions are explicit in [models/README.md](../models/README.md). No larger model weights, GPU changes, persistent credentials, system security/network settings, frontend or deployment were introduced.
