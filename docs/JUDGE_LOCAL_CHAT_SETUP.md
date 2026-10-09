# Try Nook's local text conversation

This guide targets the accepted expanded Nook source, **112-file manifest `a193c89c0938529adba9d08aeb54f4ce0f316a7dd81be2e280775f4e1abc46cd`**, frozen source ZIP SHA256 **`49d64c8b0b57f2c8fb5a5525d52bef56ccc4e0cb78c16ace9b98c8362342a0e3`**. Use this repository revision with the linked source inventory; historical baseline commits do not contain this chat implementation. This document and its readiness helper are a separate documentation overlay, outside that source manifest.

The reference platform is **Linux x86-64, Python 3.11 and Ollama 0.30.6**, with Bash or zsh. Application metadata allows Python 3.11–3.14, but the accepted run used CPython 3.11.15. Native Windows is currently blocked by Nook's POSIX file locking/storage. macOS, WSL and other architectures have not passed this recipe. A phone-sized browser view is not on-phone inference.

**Verification boundary:** the app and cached model completed a real two-turn HTTP smoke on one existing Linux installation. The fresh dependency install, ordinary model pull and the exact relocated setup below have not yet been run end-to-end. The readiness helper has been statically checked only. The three-prompt browser procedure remains a verification step, not a promised result.

## 1. Prepare the source and Python environment

Clone this public repository into a folder you own, or extract its source archive, and open a terminal in that folder. The folder must contain `app/`, `pyproject.toml` and `requirements.lock`. Use a new virtual environment:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip check
```

These commands download application and test dependencies; they do not install voice models. Do not skip hash verification if an install fails. Record the missing package/platform error instead. Fresh-machine package availability and installation are still unverified. This source archive is not an offline installer.

Install **Ollama 0.30.6** from its [official release](https://github.com/ollama/ollama/releases/tag/v0.30.6), using the installation method appropriate to your Linux system. Put `ollama` on your PATH. Installation of the runtime itself is an operator step, and was not clean-installed for this acceptance. No cloud account or API key is required for the local model. See [Ollama's local quickstart](https://docs.ollama.com/quickstart).

## 2. Start a dedicated local model runtime

In terminal A, run:

```sh
umask 077
mkdir -p "$HOME/.local/share/nook-judge/models"
export OLLAMA_MODELS="$HOME/.local/share/nook-judge/models"
export OLLAMA_HOST="127.0.0.1:11435"
export OLLAMA_NO_CLOUD=1
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_CONTEXT_LENGTH=2048
export OLLAMA_LLM_LIBRARY=cpu_avx2
export OLLAMA_VULKAN=0
export CUDA_VISIBLE_DEVICES=""
export ROCR_VISIBLE_DEVICES=-1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
ollama serve
```

Keep this terminal open. These are process-local settings; no system service, firewall or OS protection needs changing. The CPU configuration above matches the accepted AVX2-capable Linux host. Do not infer compatibility with CPUs lacking AVX2 or Apple Silicon. The API additionally requests zero GPU layers and two CPU threads per generation. This is a tested configuration, not a RAM or temperature guarantee.

The dedicated port avoids Nook's reserved default Ollama port. If 11435 is occupied, choose another unused port between 1024 and 65535, excluding 11434 and the app port, and use the same value in every relevant command/check. Do not stop an unrelated service to free it.

In terminal B, explicitly download the exact model once:

```sh
OLLAMA_HOST="127.0.0.1:11435" ollama pull qwen2.5:0.5b-instruct-q4_K_M
```

This is a network/download step. The accepted official manifest describes **397,821,319 bytes of model/config/template/license blobs**, plus an 857-byte manifest; transport overhead and any runtime/dependency downloads are additional. The ordinary `ollama pull` path has not been verified by this project; acceptance used independently size/hash-verified artifacts. The server in terminal A determines where pulled models are stored.

Model identity: [official `qwen2.5:0.5b-instruct-q4_K_M`](https://ollama.com/library/qwen2.5:0.5b-instruct-q4_K_M), Apache-2.0, expected manifest digest:

```text
a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67
```

Nook rejects a different digest. Tags can change; do not weaken the pin or silently substitute `latest`, a larger Qwen model, or a cloud model. Retain the supplied official manifest and model license. [Ollama documents `serve` and `pull`](https://docs.ollama.com/cli), [custom model folders and local-only mode](https://docs.ollama.com/faq), and the [CPU library override](https://docs.ollama.com/troubleshooting).

## 3. Start Nook and check configuration

In terminal B, from the extracted source folder:

```sh
umask 077
export APP_DATA_DIR="$HOME/.local/share/nook-judge/data"
export APP_PORT=8765
export APP_CHAT_ENABLED=1
export APP_CHAT_PORT=11435
export APP_CHAT_TIMEOUT=25
export APP_VOICE_ENABLED=0
export APP_VISION_DISABLED=1
export APP_TEXT_MODEL=""
export APP_POI_DOWNLOAD_ENABLED=0
.venv/bin/python -m app
```

Keep terminal B open. `APP_DATA_DIR` is a dedicated persistent judge store: use only invented demo records. Restarting preserves confirmed memories; conversation context is temporary RAM and is lost on restart. The app listens only on this computer's loopback address. Do not expose it to the internet or change its binding for this recipe.

In terminal C, from the same source folder, with the accompanying helper staged at `scripts/check_chat_ready.py`:

```sh
.venv/bin/python scripts/check_chat_ready.py --app-port 8765 --model-port 11435
```

The helper performs bounded read-only GETs to `127.0.0.1` for the runtime version, installed model digest and Nook configuration. It does not start services, download anything or generate a reply. Success prints `configuration_and_model_identity_passed: true` and `inference_tested: false`. Nook's own status also reports configuration rather than live model acceptance. The [official model-list API](https://docs.ollama.com/api/tags) supplies the model digest.

Open **http://127.0.0.1:8765/** on this computer. Optional voice, camera/visual inference and external area downloads remain disabled in this guide.

## 4. Three-prompt smoke test

First create one invented record through **Remember**: name **blue keys**, place **Desk drawer**. Review the item/place and explicitly **Send** to save. Confirm it appears in Saved. Do this before starting the conversation, because a memory write invalidates existing chat context.

Return to Talk. Send these prompts in order without navigating away, restarting or saving another memory between them:

| Prompt | What to verify |
|---|---|
| `Write a sentence about a fictional person named Mira holding a green kite.` | A real generated reply appears, labeled generated/unverified. It is not stored as an item. |
| `What was her name and what color was the kite?` | The reply refers to Mira and green using the preceding turn. Check the current response, not canned expected text. |
| `Where are my blue keys?` | A saved-record result shows Desk drawer with last-recorded provenance, rather than a model guess. |

For technical verification, the browser's Network panel shows each `POST /api/chat` response. The first two must have `kind:"generated"`, `inference_used:true`, `reply_authority:"generated_unverified"`, `persisted:false`, and the same `context_id`. The third must have `kind:"memory"`, `inference_used:false`, `reply_authority:"saved_records"`, and `recall.items[0].location:"Desk drawer"`. Record actual outputs and timings; do not replace failures with scripted replies.

The accepted HTTP smoke took 5.452s and 4.370s for the two generated replies on one laptop. The follow-up repeated the first sentence while retaining the correct name/color. This demonstrates narrow context use, not broad conversational quality, guaranteed latency or native-mobile performance. A different prompt may fail or produce an incorrect answer. Current real generated speech and fresh voice installation remain outside acceptance.

## Stop or recover

- A connection/readiness failure means first inspect the two terminal logs and confirm matching ports, runtime version, enabled chat and model digest. No automatic installer or cloud fallback runs.
- On a 25-second model deadline, Nook returns a visible timeout; browser requests allow 35 seconds. Retry deliberately after confirming the runtime, using a fresh chat context when the prior one expired/failed. Do not raise deadlines to conceal a stalled call.
- If the model returns an invalid response, retain that failure. Generated replies are unverified and cannot authorize memory changes or tool execution.
- Stop Nook and the dedicated Ollama process with Ctrl-C in terminals B and A. This leaves the judge's confirmed records and model files available for the next launch. Nook's delete controls require explicit confirmation; do not delete a shared store merely to repeat the demo.

The accepted run used a separate model-capable resource supervisor specific to the original Linux sensor layout. That supervisor is not included in this source snapshot; these commands do not reproduce its monitoring or establish resource acceptance on another machine. Preserve OS/hardware protections. The older models-off software guard is not a substitute for model monitoring.
