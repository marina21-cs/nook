"""Deterministic allowlist-only v1 source export; no network or credential reads."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "appbuilderss-v1/"
DOCS = [
    "NOOK_INTEGRATION_REPORT.md",
    "NOOK_JUDGE_REPRODUCIBILITY.md",
    "voice/SETUP.md",
    "voice/setup-manifest.json",
    "NOOK_EXPANDED_V1_CHECKPOINT.md",
    "NOOK_FEATURE_COVERAGE.md",
    "NOOK_NEARBY_BACKEND.md",
    "NOOK_TEST_POLICY_REASSESSMENT.md",
    "NOOK_CAPTURE_HANDOFF.md",
    "BACKEND_IMPLEMENTATION_PLAN.md",
    "V1_UI_BACKEND_CONTRACT.md",
    "docs/PRODUCT_NAME_STATUS.md",
    "docs/mobile-ui-reference/TABLER-LICENSE",
    "deliverables/nook-integration/README.md",
    "deliverables/nook-integration/browser-results.json",
    "deliverables/nook-integration/source-hashes.json",
    "deliverables/nook-integration/talk-desktop.png",
    "deliverables/nook-integration/capture-desktop.png",
    "deliverables/nook-integration/saved-mobile.png",
    "deliverables/nook-integration/recall-mobile-dark.png",
    "deliverables/nook-integration/recall-desktop.png",
    "deliverables/nook-integration/onboarding-mobile.png",
    "release/v1/voice-dependency-provenance.json",
    "voice/artifacts/whisper/README.md",
    "V1_RELEASE_CHECKLIST.md",
    "V1_DEMO_SCRIPT.md",
    "V1_REPRODUCE.md",
    "V1_PROVENANCE.md",
    "DEMO_RUNBOOK.md",
    "FRONTEND_IMPLEMENTATION_REPORT.md",
    "BACKEND_STATUS.md",
    "BACKEND_QA_REPORT.md",
    "pyproject.toml",
    "requirements.lock",
    ".gitignore",
    "docs/API.md",
    "docs/BACKEND_REQUIREMENTS_TEST_MATRIX.md",
    "docs/backend-phase-http.json",
    "models/README.md",
    "models/LICENSE",
    "voice/artifacts/manifest.json",
    "voice/evidence/dependencies.json",
    "voice/evidence/install-input-manifest.json",
    "voice/evidence/kokoro-readback-16k.wav",
    "tests/fixtures/vision/keys.jpg",
    "tests/fixtures/vision/README.md",
    "tests/fixtures/vision/manifest.json",
]
PATTERNS = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"\b(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})\b",
    rb"(?i)(?:x-amz-signature|x-goog-signature|sig=)[a-z0-9%]{24,}",
]


def payload():
    paths = {ROOT / name for name in DOCS}
    for directory, extensions in [
        ("app", {".py", ".sql", ".html", ".css", ".js"}),
        ("scripts", {".py", ".cjs"}),
        ("tests", {".py", ".mjs"}),
        ("voice/licenses", {".txt", ".md"}),
    ]:
        paths.update(p for p in (ROOT / directory).rglob("*") if p.suffix in extensions)
    result, sanitized = {}, []
    for p in sorted(paths):
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing, linked or outside payload: {p.name}")
        relative = p.relative_to(ROOT).as_posix()
        if any(
            part in {"__pycache__", ".git", ".venv", "runtime", "wheels", ".demo-data"}
            for part in p.relative_to(ROOT).parts
        ):
            continue
        raw = p.read_bytes()
        if relative == "tests/fixtures/vision/keys.jpg":
            expected = json.loads((ROOT / "tests/fixtures/vision/manifest.json").read_text())[
                "keys.jpg"
            ]["sha256"]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Public photo fixture identity changed")
        if relative == "voice/evidence/kokoro-readback-16k.wav":
            if (
                hashlib.sha256(raw).hexdigest()
                != "76da9b0d60504ee41e7c1aa00cbeb0756ec6885961dce94075e2b63021b087d2"
            ):
                raise ValueError("Synthetic speech fixture identity changed")
        if p.suffix not in {".jpg", ".wav", ".png"}:
            text = raw.decode("utf-8")
            # Only exported documentation/provenance is sanitized; canonical source stays intact.
            if p.suffix in {".md", ".json", ".lock", ".txt"}:
                clean = text.replace(str(ROOT), ".").replace(str(Path.home()), "~")
                if clean != text:
                    sanitized.append(relative)
                raw = clean.encode()
            if any(re.search(pattern, raw) for pattern in PATTERNS):
                raise ValueError(f"Potential secret in allowlisted payload: {relative}")
            if str(Path.home()).encode() in raw:
                raise ValueError(f"Personal absolute path remains: {relative}")
        result[relative] = raw
    result["README.md"] = result["V1_REPRODUCE.md"]
    manifest = {
        "release": "hackathon-v1-20261009",
        "sanitized_text_paths": sanitized,
        "files": [
            {"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in sorted(result.items())
        ],
    }
    result["SOURCE_MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    result["SHA256SUMS"] = "".join(
        f"{f['sha256']}  {f['path']}\n" for f in manifest["files"]
    ).encode()
    return result, manifest


def build(destination):
    if destination.exists():
        raise ValueError("Refusing to overwrite a release archive")
    files, manifest = payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + name, date_time=(2026, 10, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist())) == len(files)
        for name, raw in files.items():
            assert z.read(PREFIX + name) == raw
        assert all(
            name.startswith(PREFIX) and ".." not in Path(name).parts for name in z.namelist()
        )
    return {
        "archive": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "payload_files": len(manifest["files"]),
        "entries": len(files),
        "sanitized_text_paths": manifest["sanitized_text_paths"],
        "zip_crc_and_payload_hashes_verified": True,
        "secret_pattern_scan": "passed on explicit allowlist; not a universal proof",
        "excluded": [
            "credentials/env files",
            "personal data/databases",
            "raw resource/log histories",
            "Library receipts",
            "venvs",
            "wheels",
            "model weights",
            "browsers",
            "git",
            "Devin snapshots",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
