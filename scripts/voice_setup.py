"""Explicit pinned voice provisioning; standard library only, offline by default.

No imports of models and no implicit downloads. Supports CPython 3.11 Linux x86_64.
Inventory, downloads and offline installation are separate operator actions.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "voice/setup-manifest.json"
HOSTS = {
    "files.pythonhosted.org",
    "download.pytorch.org",
    "download-r2.pytorch.org",
    "huggingface.co",
    "github.com",
    "release-assets.githubusercontent.com",
}
CHUNK = 32768


def validate_url(url, redirect=False):
    if not isinstance(url, str):
        raise ValueError("Invalid artifact URL")
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    allowed = host in HOSTS or (
        redirect and (host.endswith(".hf.co") or host.endswith(".huggingface.co"))
    )
    if (
        parsed.scheme != "https"
        or not allowed
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Unapproved artifact source or redirect")
    if not redirect and (parsed.query or parsed.fragment):
        raise ValueError("Manifest sources must be stable URLs without credentials/query/fragment")


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text())
    if (
        not isinstance(data, dict)
        or data.get("schema") != 1
        or not isinstance(data.get("files"), list)
        or not data["files"]
    ):
        raise ValueError("Invalid setup manifest")
    seen = set()
    for entry in data["files"]:
        if (
            not isinstance(entry, dict)
            or not {"path", "kind", "bytes", "sha256", "url"} <= entry.keys()
        ):
            raise ValueError("Incomplete artifact entry")
        name = entry["path"]
        if not isinstance(name, str):
            raise ValueError("Unsafe artifact path")
        parts = PurePosixPath(name).parts
        if (
            not isinstance(name, str)
            or not parts
            or name != str(PurePosixPath(name))
            or any(p in {"..", "."} for p in parts)
            or "\\" in name
        ):
            raise ValueError("Unsafe artifact path")
        if entry["kind"] == "package":
            if len(parts) != 2 or parts[0] != "packages" or not name.endswith((".whl", ".tar.gz")):
                raise ValueError("Invalid package path")
        elif entry["kind"] == "model":
            if len(parts) < 3 or parts[0] != "artifacts":
                raise ValueError("Invalid model path")
        else:
            raise ValueError("Unsupported artifact kind")
        if name in seen:
            raise ValueError("Duplicate artifact path")
        seen.add(name)
        if (
            type(entry["bytes"]) is not int
            or entry["bytes"] <= 0
            or not isinstance(entry["sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
        ):
            raise ValueError("Invalid size or digest")
        validate_url(entry["url"])
    if sum(e["bytes"] for e in data["files"]) != data.get("total_payload_bytes"):
        raise ValueError("Manifest total mismatch")
    return data


def destination(root, entry):
    root = Path(root).absolute()
    if root.is_symlink():
        raise ValueError("Voice root cannot be a symlink")
    path = root / entry["path"]
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escapes voice root")
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError("Artifact path contains a symlink")
    return path


def verified(path, entry):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["bytes"]:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == entry["sha256"]


def selected(data, group):
    return [e for e in data["files"] if group == "all" or e["kind"] == group]


def inventory(root, data, group="all"):
    files = []
    for entry in selected(data, group):
        path = destination(root, entry)
        files.append(
            {
                "path": entry["path"],
                "bytes": entry["bytes"],
                "present_size_matches_unverified": path.is_file()
                and path.stat().st_size == entry["bytes"],
                "url": entry["url"],
                "sha256": entry["sha256"],
            }
        )
    return {
        "target": data["target"],
        "network_used": False,
        "total_payload_bytes": sum(e["bytes"] for e in files),
        "missing_or_wrong_size_bytes": sum(
            e["bytes"] for e in files if not e["present_size_matches_unverified"]
        ),
        "note": "Presence/size is not integrity acceptance; download/install/verify checks full SHA256. No existing file is overwritten.",
        "files": files,
    }


class SourceRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_url(newurl, redirect=True)
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        # urllib otherwise drains the redirect body with an unbounded read.
        if fp is not None:
            fp.close()
        return redirected


def open_source(url):
    validate_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), SourceRedirects())
    return opener.open(
        urllib.request.Request(
            url, headers={"User-Agent": "Nook-pinned-voice-setup/1", "Accept-Encoding": "identity"}
        ),
        timeout=20,
    )


@contextmanager
def exclusive(root):
    # Only this app-owned setup lock; never process termination or OS configuration.
    import fcntl

    root = Path(root)
    if root.is_symlink():
        raise ValueError("Voice root cannot be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".setup.lock"
    if lock.is_symlink():
        raise ValueError("Setup lock cannot be a symlink")
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def download(root, data, group, *, allow_network=False, budget=0, opener=open_source):
    if not allow_network:
        raise ValueError(
            "Download requires --allow-network and an explicit --max-download-bytes budget"
        )
    entries = selected(data, group)
    missing = []
    for entry in entries:
        path = destination(root, entry)
        if path.exists():
            if not verified(path, entry):
                raise ValueError(
                    "Existing artifact failed verification; preserved: " + entry["path"]
                )
        else:
            missing.append(entry)
    required = sum(e["bytes"] for e in missing)
    if type(budget) is not int or budget < required:
        raise ValueError(f"Budget insufficient: {required} bytes required")
    received = 0
    with exclusive(root):
        for entry in missing:
            path = destination(root, entry)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError("Artifact appeared during setup; retry inventory")
            part = path.with_name(path.name + ".part")
            if part.exists() or part.is_symlink():
                raise ValueError("Partial file exists; inspect before retrying: " + str(part))
            own = False
            try:
                digest = hashlib.sha256()
                count = 0
                started = time.monotonic()
                with part.open("xb") as output:
                    own = True
                    with opener(entry["url"]) as response:
                        if getattr(response, "status", 200) != 200 or response.headers.get(
                            "Content-Encoding", "identity"
                        ) not in {"identity", ""}:
                            raise ValueError("Unexpected source response")
                        length = response.headers.get("Content-Length")
                        if length is not None and (
                            not length.isdigit() or int(length) != entry["bytes"]
                        ):
                            raise ValueError("Source length differs from manifest")
                        while count < entry["bytes"]:
                            if time.monotonic() - started > 300:
                                raise TimeoutError("Artifact download deadline")
                            chunk = response.read(min(CHUNK, entry["bytes"] - count))
                            if not chunk:
                                break
                            count += len(chunk)
                            received += len(chunk)
                            if count > entry["bytes"] or received > budget:
                                raise ValueError("Download budget exceeded")
                            digest.update(chunk)
                            output.write(chunk)
                        if count != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                            raise ValueError("Artifact size or SHA256 mismatch")
                    output.flush()
                    os.fsync(output.fileno())
                if path.exists():
                    raise ValueError("Refusing to overwrite artifact")
                part.replace(path)
                own = False
            finally:
                if own:
                    part.unlink(missing_ok=True)
    return {
        "downloaded_bytes": received,
        "downloaded_files": len(missing),
        "verified_cached_files": len(entries) - len(missing),
    }


def verify(root, data, group="all"):
    entries = selected(data, group)
    for entry in entries:
        if not verified(destination(root, entry), entry):
            raise ValueError("Missing/invalid artifact: " + entry["path"])
    return {
        "verified_files": len(entries),
        "verified_bytes": sum(e["bytes"] for e in entries),
        "network_used": False,
    }


def require_platform():
    libc, version = platform.libc_ver()
    if (
        platform.python_implementation() != "CPython"
        or sys.version_info[:2] != (3, 11)
        or sys.platform != "linux"
        or platform.machine() != "x86_64"
        or libc != "glibc"
        or tuple(map(int, version.split(".")[:2])) < (2, 28)
    ):
        raise ValueError(
            "Pinned packages require CPython 3.11, Linux x86_64, glibc >=2.28; other platforms are unverified"
        )


def install(root, data, *, run=subprocess.run, platform_check=require_platform):
    platform_check()
    root = Path(root).absolute()
    verify(root, data, "package")
    runtime = root / "runtime"
    if runtime.exists() or runtime.is_symlink():
        raise ValueError(
            "Runtime already exists; preserved. Choose a fresh checkout for installation."
        )
    # Paths inside scripts/shebangs must remain at their final destination.
    # On failure keep the marked incomplete runtime for explicit operator inspection.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PIP_", "PYTHON", "HF_", "TRANSFORMERS_"))
    }
    env.update(
        PIP_NO_INDEX="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    packages = selected(data, "package")
    bootstrap = next((e for e in packages if e.get("name") == "setuptools"), None)
    if bootstrap is None:
        raise ValueError("Pinned setuptools bootstrap missing")
    with exclusive(root):
        if runtime.exists():
            raise ValueError("Runtime appeared during setup")
        runtime.mkdir()
        marker = runtime / ".nook-setup-incomplete"
        marker.write_text("Installation incomplete; do not enable voice.\n")
        run([sys.executable, "-m", "venv", str(runtime)], check=True, timeout=60, env=env)
        python = runtime / "bin/python"
        common = [
            str(python),
            "-I",
            "-m",
            "pip",
            "--isolated",
            "install",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--require-hashes",
        ]
        with tempfile.TemporaryDirectory(prefix="nook-voice-lock-", dir=root) as folder:

            def lock(name, entries):
                path = Path(folder) / name
                path.write_text(
                    "".join(
                        destination(root, e).as_uri() + " --hash=sha256:" + e["sha256"] + "\n"
                        for e in entries
                    )
                )
                return str(path)

            run(
                [*common, "-r", lock("bootstrap.lock", [bootstrap])],
                check=True,
                timeout=60,
                env=env,
            )
            run([*common, "-r", lock("voice.lock", packages)], check=True, timeout=300, env=env)
        run(
            [str(python), "-I", "-m", "pip", "--isolated", "check"], check=True, timeout=30, env=env
        )
        # Preserve notices from all installed distributions; do not import models.
        marker.unlink()
    return {
        "runtime": str(runtime),
        "installed_packages": len(packages),
        "network_used": False,
        "models_loaded": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inventory", "download", "verify", "install"])
    parser.add_argument("--group", choices=["all", "package", "model"], default="all")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--max-download-bytes", type=int, default=0)
    args = parser.parse_args(argv)
    root = ROOT / "voice"
    try:
        data = load_manifest()
        if args.command == "inventory":
            result = inventory(root, data, args.group)
        elif args.command == "download":
            result = download(
                root,
                data,
                args.group,
                allow_network=args.allow_network,
                budget=args.max_download_bytes,
            )
        elif args.command == "verify":
            result = verify(root, data, args.group)
        else:
            result = install(root, data)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
        print(f"Voice setup stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
