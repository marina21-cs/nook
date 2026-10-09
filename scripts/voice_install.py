"""Offline install of previously approved and verified local voice dependencies."""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

root = Path("voice")
plan = json.loads((root / "evidence/download-plan.json").read_text())
# Pin every artifact's observed hash before install, including the official spaCy
# release whose upstream API supplies no digest. This is not an upstream signature.
verified = []
for entry in plan["files"]:
    path = root / entry["path"]
    if path.stat().st_size != entry["bytes"]:
        raise ValueError("Artifact size changed")
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    if entry.get("sha256") and digest != entry["sha256"]:
        raise ValueError("Artifact digest changed")
    verified.append(
        {
            "path": entry["path"],
            "bytes": entry["bytes"],
            "sha256": digest,
            "source": entry["url"],
            "upstream_sha256_available": bool(entry.get("sha256")),
        }
    )
(root / "evidence/install-input-manifest.json").write_text(json.dumps(verified, indent=2) + "\n")
# Inspect source-only docopt setup: plain setuptools metadata for one module.
source = next((root / "wheels").glob("docopt-*.tar.gz"))
with tarfile.open(source) as t:
    member = next(x for x in t.getmembers() if x.name.endswith("/setup.py"))
    code = t.extractfile(member).read().decode()
    (root / "evidence/docopt-setup-reviewed.py.txt").write_text(code)
    print(code)
    # Reject network/custom-command build hooks before this deliberately tiny offline build.
    assert "cmdclass" not in code and "subprocess" not in code and "urllib" not in code
for path in (root / "wheels").glob("*.whl"):
    with zipfile.ZipFile(path) as z:
        for index, name in enumerate(z.namelist()):
            if (
                ("license" in name.lower() or "copying" in name.lower())
                and z.getinfo(name).file_size < 1000000
                and not name.endswith("/")
            ):
                (root / "licenses" / f"{path.stem}-{index}.txt").write_bytes(z.read(name))
subprocess.run([sys.executable, "-m", "ensurepip"], check=True, timeout=30)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--ignore-installed",
        "benchmarks/smolvlm-500m-2026-10-09/wheels/setuptools-80.9.0-py3-none-any.whl",
    ],
    check=True,
    timeout=30,
)
wheels = [str(root / f["path"]) for f in plan["files"] if f["path"].startswith("wheels/")]
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--ignore-installed",
        "--no-build-isolation",
        *wheels,
    ],
    check=True,
    timeout=90,
    env={**os.environ, "PIP_NO_INDEX": "1"},
)
subprocess.run([sys.executable, "-m", "pip", "check"], check=True, timeout=15)
# Imports verify runtime wiring but intentionally do not instantiate any speech model.
subprocess.run(
    [
        sys.executable,
        "-c",
        'import torch,transformers,kokoro,spacy,espeakng_loader; print(torch.__version__,transformers.__version__); nlp=spacy.load("en_core_web_sm"); print(nlp.meta["version"]); import ctypes; ctypes.CDLL(espeakng_loader.get_library_path()); print(espeakng_loader.get_library_path()); p=kokoro.KPipeline(lang_code="a",model=False,device="cpu",repo_id="hexgrad/Kokoro-82M"); print(p.g2p("blue keys")[0])',
    ],
    check=True,
    timeout=30,
    env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
)
print("INSTALL_IMPORTS_PASSED; NO SPEECH MODEL LOADED")
