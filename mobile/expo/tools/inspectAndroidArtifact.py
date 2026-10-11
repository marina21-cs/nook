"""Inspect a compiled diagnostic APK without installing or opening a device."""

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("sdk", type=Path)
    parser.add_argument("prebundle_receipt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    tools = args.sdk / "build-tools/36.0.0"
    commands = {}

    def run(name, executable, *arguments):
        command = [str(executable), *map(str, arguments)]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=45,
            env={**os.environ, "JAVA_OPTS": "-Xmx128m -XX:ActiveProcessorCount=1"},
            check=False,
        )
        output = result.stdout + result.stderr
        (args.output / f"{name}.txt").write_text(output)
        commands[name] = {"command": command, "exit_code": result.returncode}
        if result.returncode:
            raise RuntimeError(f"{name} failed; preserve its output for review")
        return output

    badging = run("badging", tools / "aapt2", "dump", "badging", args.apk)
    permission_dump = run("permissions", tools / "aapt2", "dump", "permissions", args.apk)
    manifest = run(
        "manifest", tools / "aapt2", "dump", "xmltree", args.apk, "--file", "AndroidManifest.xml"
    )
    backup = run(
        "backup-rules",
        tools / "aapt2",
        "dump",
        "xmltree",
        args.apk,
        "--file",
        "res/xml/nook_data_extraction_rules.xml",
    )
    signing = run("signing", tools / "apksigner", "verify", "--verbose", "--print-certs", args.apk)
    run("alignment", tools / "zipalign", "-c", "-P", "16", "-v", "4", args.apk)
    prebundle = json.loads(args.prebundle_receipt.read_text())
    permissions = sorted(set(re.findall(r"uses-permission[^\n]*name='([^']+)'", permission_dump)))
    forbidden = {
        "android.permission.RECORD_AUDIO",
        "android.permission.CAMERA",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
    }
    if set(permissions) & forbidden:
        raise RuntimeError("Packaged permission requires review")
    allowed = {
        "android.permission.INTERNET",
        "android.permission.VIBRATE",
        "android.permission.ACCESS_NETWORK_STATE",
        "dev.nook.local.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
    }
    if not permissions or set(permissions) - allowed:
        raise RuntimeError("Unexpected diagnostic permission set; review the captured manifest")
    if (
        "package: name='dev.nook.local'" not in badging
        or "sdkVersion:'24'" not in badging
        or "targetSdkVersion:'36'" not in badging
    ):
        raise RuntimeError("Unexpected package/SDK tuple")
    if not re.search(r"android:allowBackup[^\n]*(?:0x0|false)(?:\s|$)", manifest):
        raise RuntimeError("Packaged allowBackup is not false")
    if "android:dataExtractionRules" not in manifest or "android:fullBackupContent" not in manifest:
        raise RuntimeError("Backup exclusions are absent from the packaged manifest")
    if not re.search(r"android:fullBackupContent[^\n]*(?:0x0|false)(?:\s|$)", manifest):
        raise RuntimeError("Packaged legacy backup is not disabled")
    if not re.search(
        r"expo.modules.updates.ENABLED[^\n]*\n\s*A: android:value[^\n]*(?:0x0|false)(?:\s|$)",
        manifest,
    ):
        raise RuntimeError("Packaged update flag is not disabled")
    if (
        not all(
            f"E: {route}" in backup
            for route in ("cloud-backup", "device-transfer", "cross-platform-transfer")
        )
        or backup.count("E: exclude") != 27
    ):
        raise RuntimeError("Expected all 27 packaged backup/transfer exclusions")
    if "application-debuggable" in badging:
        raise RuntimeError("Expected a release-mode diagnostic APK")

    native_libraries = []
    with zipfile.ZipFile(args.apk) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("APK ZIP integrity failed")
        bundle = archive.read("assets/index.android.bundle")
        if digest(bundle) != prebundle["bundleSha256"] or bundle[:8].hex() != "c61fbc03c103191f":
            raise RuntimeError("Packaged Hermes bundle does not match the reviewed source receipt")
        for path in sorted(archive.namelist()):
            if not path.startswith("lib/") or not path.endswith(".so"):
                continue
            binary = archive.read(path)
            if binary[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", binary, 18)[0] != 183:
                raise RuntimeError(f"Expected an ARM64 ELF library: {path}")
            offset = struct.unpack_from("<Q", binary, 32)[0]
            size, count = struct.unpack_from("<HH", binary, 54)
            alignments = [
                struct.unpack_from("<Q", binary, offset + index * size + 48)[0]
                for index in range(count)
                if struct.unpack_from("<I", binary, offset + index * size)[0] == 1
            ]
            native_libraries.append(
                {
                    "path": path,
                    "bytes": len(binary),
                    "sha256": digest(binary),
                    "load_segment_alignments": alignments,
                    "load_segments_at_least_16k": bool(alignments) and min(alignments) >= 16384,
                }
            )
        if not native_libraries or any(
            not item["path"].startswith("lib/arm64-v8a/") for item in native_libraries
        ):
            raise RuntimeError("Unexpected diagnostic ABI set")
    certificate = re.search(r"Signer #1 certificate SHA-256 digest: ([a-f0-9]+)", signing)
    if not certificate or len(certificate.group(1)) != 64:
        raise RuntimeError("Signer fingerprint was not verified")
    artifact = args.output / "nook-local-memory-arm64-diagnostic.apk"
    shutil.copyfile(args.apk, artifact)
    report = {
        "utc": datetime.now(UTC).isoformat(),
        "apk": str(artifact.resolve()),
        "bytes": artifact.stat().st_size,
        "sha256": digest(artifact.read_bytes()),
        "variant": "release-mode diagnostic; existing public template debug key",
        "abi": ["arm64-v8a"],
        "application_id": "dev.nook.local",
        "min_sdk": 24,
        "target_sdk": 36,
        "signer_certificate_sha256": certificate.group(1) if certificate else None,
        "permissions": permissions,
        "bundle_sha256": digest(bundle),
        "bundle_bytes": len(bundle),
        "bundle_receipt": prebundle,
        "native_libraries": native_libraries,
        "commands": commands,
        "all_load_segments_at_least_16k": all(
            item["load_segments_at_least_16k"] for item in native_libraries
        ),
        "installed_or_launched": False,
        "device_performance_measured": False,
        "scope": "static artifact inspection; OS transport, installed SQLite and offline lifecycle unrun",
    }
    (args.output / "artifact-inspection.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"bundle_receipt", "native_libraries", "commands"}
            }
        )
    )


if __name__ == "__main__":
    main()
