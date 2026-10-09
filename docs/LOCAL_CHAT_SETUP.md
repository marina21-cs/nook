# Optional genuine local chat: accepted Linux configuration

Start with the [README typed setup](../README.md#quick-start). The default leaves chat
off and needs no model. Enabling this optional path needs a separately provisioned
[Ollama 0.30.6](https://github.com/ollama/ollama/releases/tag/v0.30.6) CPU runtime and the
exact [Qwen2.5 0.5B Instruct Q4_K_M model](https://ollama.com/library/qwen2.5:0.5b-instruct-q4_K_M).
The app never downloads models or starts a daemon automatically. This is a tested existing
Linux laptop configuration, not a clean-machine installer or Mac/Windows/phone support claim.

## Model identity and acquisition boundary

Expected manifest SHA256: `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`. Official registry URLs, layer sizes and hashes
are in [model provenance](../models/qwen2.5-0.5b-instruct-q4_K_M/provenance.json);
the exact manifest and Apache-2.0 license are retained alongside it. Model layers total
397,821,319 bytes, plus the 857-byte manifest and transfer overhead. Tags may change;
verify the exact manifest and all layer hashes, not just the model name. The application
also requires the expected digest returned by the dedicated runtime's model listing.

Weights, acquisition caches, runtimes and private resource logs are excluded. Provision
the exact official artifacts separately or use a trusted offline copy of that model-only
Ollama cache. Keep it private at an operator-chosen path such as `.nook-chat-models`.
This source export does not contain an automatic model installer; package acquisition and
fresh-machine setup remain separate. Do not point at another user's service-owned cache.

## Accepted environment

The dedicated runtime listens only on `127.0.0.1:11435`; the app stays on its own loopback
port. The accepted run used cloud disabled, one model/parallel request, two CPU threads,
2048 context tokens and at most 256 output tokens. GPU use was disabled. These are process
environment settings, not hardware/firewall changes. A model-capable resource supervisor
with the accepted alarm/configured-high, CPU/RSS/memory/swap and cleanup policy was used;
the older models-off video supervisor is not an inference guard. Do not present the shell
forms below as a replacement for that monitored run. No command was executed in packaging.

For an already verified private model cache, the runtime's Linux Bash/zsh environment is:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
OLLAMA_MODELS="$PWD/.nook-chat-models" OLLAMA_HOST=127.0.0.1:11435 \
OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_CONTEXT_LENGTH=2048 OLLAMA_LLM_LIBRARY=cpu_avx2 OLLAMA_VULKAN=0 \
CUDA_VISIBLE_DEVICES='' ROCR_VISIBLE_DEVICES=-1 ollama serve
```

The corresponding app configuration, in a separate terminal under the same monitored
session, is:

```sh
APP_DATA_DIR="$PWD/.chat-demo-data" APP_PORT=8765 \
APP_CHAT_ENABLED=1 APP_CHAT_PORT=11435 APP_CHAT_TIMEOUT=25 \
APP_VISION_DISABLED=1 APP_VOICE_ENABLED=0 APP_POI_DOWNLOAD_ENABLED=0 \
APP_TEXT_MODEL='' .venv/bin/python -m app
```

Stop the app and dedicated runtime with Ctrl+C in their own terminals. Do not stop an
unrelated Ollama service. No ports are exposed to another device by these commands.

## Proven behavior and limits

The accepted API smoke asked for a fictional Mira with a green kite, then her name and
kite color. Two real responses took 5.452s and 4.370s. They used the same ephemeral context;
the follow-up repeated the original sentence while retaining the right facts. These are
observed complete-response latencies, not performance guarantees. Generated text is
explicitly unverified and cannot write memories, run tools, browse or send messages.

Context is bounded RAM-only state: a 300-second lifetime, at most 32 active contexts and a
bounded recent history. Reset/restart invalidates it. Personal-item queries use confirmed
record lookup without model inference; missing items stay unknown. The real run verified
saved-item/pronoun lookup, reset, runtime-unavailable503, restart persistence and offline
saved recall. The readiness/status endpoint reports configuration and does not replace
this acceptance receipt.

Generated browser recording is pending. Current STT/TTS, spoken generated replies,
physical camera, general vision, Taglish speech, native phone and clean installation are
not established. [Version-specific evidence](LOCAL_CHAT_VERIFICATION.json).

## Judge recipe

The [judge local-chat guide](JUDGE_LOCAL_CHAT_SETUP.md) supplies explicit ordinary download and readiness steps, clearly marked where clean installation and runtime verification have not been completed. Its read-only helper is a separate overlay, not part of the frozen 112-file source inventory.
