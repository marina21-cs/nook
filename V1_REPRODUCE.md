> Historical baseline document. Its counts, UI steps and provisioning instructions do not describe the expanded release. See [current release and reproduction notes](docs/EXPANDED_RELEASE.md).

# Nook — reproduce the hackathon v1 source release

This is a source archive, not a self-contained offline installer. It excludes Python environments, browser binaries, weights, wheel caches, credentials, actual user records and unrelated project history. The original project and historical evidence/snapshots remain intact outside the archive.

## Existing development computer

Use the exact local commands in `DEMO_RUNBOOK.md`. All models and runtimes referenced there already exist on that computer. No new installation/download is needed. Typed mode starts without any model; voice is opt-in and resource guarded.

## Another checkout/environment

Use Python 3.11 (the tested version), create `.venv`, and install `requirements.lock` with hash checking only when package downloads are separately permitted:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
APP_DATA_DIR="$PWD/.demo-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=0 APP_TEXT_MODEL='' .venv/bin/python -m app
```

Open http://127.0.0.1:8765/ locally; Ctrl+C stops the service. These install commands are instructions, not an operation performed during release. A new machine requires its own approved dependency provisioning.

Voice additionally requires a project-local `voice/runtime/bin/python`, the exact compatible speech dependencies in `voice/evidence/dependencies.json`, and files listed by size/source/revision/SHA256 in `voice/artifacts/manifest.json`. Restore only approved matching artifacts; the application never downloads them. `voice/evidence/install-input-manifest.json` records pinned downloaded input hashes. Cached dependency reuse is identified in the dependency inventory. Model/code/voice licenses differ; retained notices and `V1_PROVENANCE.md` are authoritative for this package. No promise of full binary reproducibility across platforms is made.

## Verification

```sh
.venv/bin/python -m pytest --ignore=tests/test_vision.py
.venv/bin/ruff check app tests scripts
.venv/bin/mypy app
node scripts/frontend_audio_test.cjs
```

Browser checks require an already installed Node + Playwright + Chromium. Set `PLAYWRIGHT_MODULE` to an existing Playwright module and `CHROMIUM_EXECUTABLE` to an existing Chromium binary if the tested local cache locations do not apply. Set `APP_TEST_PYTHON` to an existing compatible Python interpreter when testing an extracted source tree without its own `.venv`. No test script installs these tools. `node scripts/nook_browser_test.cjs` creates and cleans temporary records and mocks device/provider boundaries; it does not establish real AI acceptance.

Real inference checks on the development laptop run through `scripts/voice_guard.py`, as documented in the runbook. Its unprivileged sensor policy is specific to the monitored laptop; unsupported sensors fail closed. Do not remove or relax guards to run on a different machine. Real vision tests and optional historical tooling need excluded assets; they are outside this bounded v1 acceptance.

## Archive and publication identity

This is a publication package derived from the verified baseline ZIP, not a byte-identical repack. `PUBLICATION_MANIFEST.json` covers this staged payload except itself. The original ZIP identity and historical verification are retained in `docs/BASELINE_VERIFICATION.json`; application/test/script bytes remain identical to that baseline. Publication documentation and exclusions differ. The historical archive-builder script is retained as source, but references excluded internal reports and is not a turnkey reproduction command for this public tree. See `docs/PUBLICATION_PROVENANCE.md`.
