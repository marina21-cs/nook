# Run bounded laptop conversation

From `/home/keni/Documents/ChatGPT/appbuilderss`, use existing Node 24.19.0/dependencies, Ollama 0.30.6, pinned complete Qwen project cache and existing Ollama key. The launcher fails if these are missing/changed; it does not download or create credentials. Ports 11439 (owned Ollama) and 8081 (preview) must be free. Leave pre-existing 11434 alone.

The web export already exists. After edits, re-export under the software guard:

```sh
.venv/bin/python scripts/software_guard.py --stage laptop-web-export-next --timeout 120 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/exportWebLimited.mjs
```

Start the supervised session:

```sh
.venv/bin/python docs/candidates/local-chat-20261010/model_guard.py --stage laptop-preview-next --timeout 180 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/runLaptopPreview.mjs --existing-qwen-only
```

Open **http://127.0.0.1:8081** → **Setup → Enable laptop conversation** → Chat. Try “Hello Nook”, “For a fictional story, Mira owns a green kite”, then “What color is the kite in the story?” Generated replies are unconfirmed. “Where are my keys?” still uses SQLite source cards; saving requires its exact approval button. Use Cancel generation for an active call. Disable or Start a fresh conversation clears generated context.

The preview ends after 170 seconds, Ctrl+C or a guard abort. Only owned services stop; browser records remain. Each run needs a unique `--stage`. Private logs: `deliverables/nook-laptop-session-<timestamp>`; supervisor evidence: `docs/candidates/local-chat-20261010/evidence`. Retain configured resource/alarm limits; do not bypass or loosen the guard. One active client request, 20-second server deadline. Ordinary static `preview:web` intentionally does not enable a model.

Regression commands, each with fresh stage/output names:

```sh
.venv/bin/python scripts/software_guard.py --stage laptop-contract-next --timeout 120 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --test --test-reporter=tap --test-concurrency=1 mobile/expo/tests/*.test.mjs

.venv/bin/python scripts/software_guard.py --stage laptop-source-next --timeout 120 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tools/checkSource.mjs

NOOK_LAPTOP_BROWSER_OUTPUT=deliverables/nook-laptop-browser-next .venv/bin/python scripts/software_guard.py --stage laptop-browser-next --timeout 120 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tests/laptopBrowser.mjs

NOOK_BROWSER_OUTPUT=deliverables/nook-laptop-regression-next .venv/bin/python scripts/software_guard.py --stage laptop-regression-next --timeout 120 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tests/browserFlows.mjs

NOOK_REAL_OUTPUT=deliverables/nook-laptop-real-next .venv/bin/python docs/candidates/local-chat-20261010/model_guard.py --stage laptop-qwen-real-next --timeout 180 -- /usr/bin/taskset -c 0,1 /home/keni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node mobile/expo/tests/realLaptop.mjs
```

The managed executor needs its approved local IPC/process-metadata route; otherwise sandbox restrictions can masquerade as failures. No native build/install/download/cloud connection is part of these commands. Actual model output is distinct from browser/HTTP fixtures. [Measured receipt](LAPTOP_CONVERSATION_RECEIPT.md).
