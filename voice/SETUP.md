# Optional local voice setup

This candidate installer removes the historical dependency on private development caches. Its targeted synthetic suite passed 50 tests, including the monitor regression, under a clean resource guard. The complete deterministic backend suite passed 408 tests. A real fresh-machine installation and real current-UI voice acceptance remain pending. Typed mode requires none of these downloads.

## Supported target and prerequisites

Use CPython 3.11 on Linux x86_64 with glibc 2.28 or newer and working `venv`/`ensurepip`. Other interpreter, OS and CPU combinations have no pinned package set here. The current inference worker additionally expects Linux `/proc` and the project's monitored `k10temp`/`spd5118` sensors and fails closed if they are absent. Installation does not establish device compatibility. Do not relax guards to run on another device; that requires a separately reviewed platform implementation.

`setup-manifest.json` lists 89 package inputs and 15 model files, each with its official HTTPS URL, exact bytes and SHA256. Package inputs include the pinned setuptools bootstrap and spaCy English support model. Whisper tiny and Kokoro-82M/af_heart revisions are also retained in `artifacts/manifest.json`. No account, cloud API key or global package installation is needed.

A completely empty input cache requires **820,069,956 payload bytes**: 336,877,743 for packages and 483,192,213 for model files. HTTP/TLS overhead is additional. Extracted packages, temporary build files and the runtime require additional disk space; no measured disk/RAM ceiling is claimed. Some small model metadata files may already be included in a source export. Inventory reports existing size matches without claiming hash verification.

These are instructions for an operator who separately approves that transfer and resource use. They do not authorize a new download in the current development session, whose earlier download allowance is almost exhausted.

## Explicit online provisioning

Run from a fresh checkout's root. First inspect the manifest, sources, licenses and inventory (no network):

```sh
python3.11 scripts/voice_setup.py inventory
```

Only after approving the displayed inputs and byte allowance:

```sh
python3.11 scripts/voice_setup.py download --allow-network --max-download-bytes 820069956
python3.11 scripts/voice_setup.py verify
```

Downloads are sequential, use approved official hosts, bypass inherited proxies, verify size and SHA256 before atomic publication, and refuse to overwrite a mismatching existing file. They have a per-read timeout and bounded file deadline, no automatic retries or resume. The allowance limits downloaded artifact payload per invocation; a failed attempt still consumed network bytes. Track previous attempts before authorizing a retry. Existing `.part` files are preserved for inspection. Only a partial file created by the current failed attempt is removed.

`--group package` or `--group model` can split inventory/download/verification. Package-only provisioning can install the runtime but cannot make voice ready. Models stay optional. A trusted offline transfer can instead copy exactly the manifest-listed inputs into `voice/packages/` and `voice/artifacts/`; run verification before installation. Do not copy personal records or arbitrary caches.

## Offline install and startup

With all package files present and verified:

```sh
python3.11 scripts/voice_setup.py install
```

Installation creates `voice/runtime` at its final location, uses only local hash-pinned inputs with pip's `--no-index --no-deps --no-build-isolation --require-hashes`, and runs `pip check`. The pinned docopt source archive is built locally with pinned setuptools; other inputs are wheels. This executes trusted upstream package/build code and is not an OS network sandbox. Models are not imported or downloaded by installation. `scripts/voice_install.py` is a compatibility entrypoint for this same offline install.

An existing runtime is never replaced. A failed installation retains `.nook-setup-incomplete` for inspection and cannot be advertised as ready by the application. Use a fresh checkout for another installation attempt. Do not move an installed virtual environment: its interpreter paths/shebangs may depend on its location.

After separately installing the main app dependencies as described in `V1_REPRODUCE.md`, and only on a supported monitored device with the existing model guard satisfied:

```sh
python3.11 scripts/voice_setup.py verify
APP_DATA_DIR="$PWD/.judge-data" APP_PORT=8765 APP_VISION_DISABLED=1 APP_VOICE_ENABLED=1 APP_POI_DOWNLOAD_ENABLED=0 APP_TEXT_MODEL='' .venv/bin/python -m app
```

The app checks artifact presence/size and incomplete-install state before advertising readiness; the worker verifies full model hashes before loading. Startup does not fetch missing components. STT text remains editable and needs explicit Send; TTS is manually played. Resource guard defaults and their experimental nature are documented in `NOOK_TEST_POLICY_REASSESSMENT.md` and `DEMO_RUNBOOK.md`. A Python socket guard is not proof of OS-wide network isolation.

## Provenance and acceptance

Retain `voice/licenses/`, upstream wheel metadata/notices, `artifacts/manifest.json` and `V1_PROVENANCE.md`. Whisper code/model terms, Kokoro model/voice terms and dependency licenses differ; GPL/LGPL components are present. No blanket license for the assembled runtime is inferred.

The historical dependency inventory mistakenly recorded a partial PyTorch transfer (26,766,963 bytes) as the wheel. The corrected full input in this setup manifest is 184,053,363 bytes, SHA256 `cb06175284673a581dd91fb1965662ae4ecaba6e5c357aa0ea7bb8b84b6b7eeb`, matched against the official PyTorch CPU index and retained complete wheel. Historical evidence and the old ZIP are preserved; use the new setup manifest for installation. Eleven previously cache-only dependencies now have official pinned PyPI input hashes, and the English support model is explicitly listed.

`tests/test_voice_setup.py` uses tiny synthetic files and mocked download/install boundaries. Even when those tests pass, they do not establish actual download availability, successful upstream package installation, real inference, speech quality, Taglish accuracy, or the current browser voice flow. These require separate monitored acceptance evidence.
