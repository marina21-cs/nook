"""Resume approved voice artifacts with one connection and bounded streaming memory.

Run through scripts/voice_guard.py only after fresh recovery. Inventory mode performs
no network transfer. Saved prefixes/ranges are preserved, never redownloaded merely
because a prior supervisor stopped the process. A final expected full-file hash is
required before model files are made available to the runtime.
"""

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "voice"
PRIOR_BYTES = 1272923892
BUDGET = 2000000000
CHUNK = 32768
RANGE = 1024 * 1024


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_ledger(path, ledger):
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(ledger, indent=2) + "\n")
    staging.replace(path)


def verify(path, entry):
    if path.stat().st_size != entry["bytes"]:
        raise ValueError("Artifact size mismatch")
    sha = digest(path)
    if entry.get("sha256") and sha != entry["sha256"]:
        raise ValueError("Artifact SHA256 mismatch")
    if entry.get("git_blob_sha1"):
        blob = hashlib.sha1(b"blob " + str(entry["bytes"]).encode() + b"\0")
        with path.open("rb") as source:
            while chunk := source.read(CHUNK):
                blob.update(chunk)
        if blob.hexdigest() != entry["git_blob_sha1"]:
            raise ValueError("Official Git blob verification failed")
    return sha


def sources(entry):
    target = VOICE / entry["path"]
    result = []
    prefix = target.with_suffix(target.suffix + ".part")
    if prefix.exists():
        result.append((0, prefix.stat().st_size, prefix))
    folder = VOICE / "artifacts/ranges" / target.name
    if folder.exists():
        for path in sorted(folder.iterdir()):
            match = re.fullmatch(r"(\d+)-(\d+)\.(bin|part)", path.name)
            if match:
                start, end = int(match[1]), int(match[2])
                length = path.stat().st_size
                if length > end - start + 1:
                    raise ValueError("Oversized retained segment")
                if length:
                    result.append((start, start + length, path))
    result.sort()
    previous = 0
    for start, end, _path in result:
        if start < previous or end > entry["bytes"]:
            raise ValueError("Overlapping or out-of-bounds retained segments")
        previous = end
    return result


def missing(entry):
    target = VOICE / entry["path"]
    if target.exists():
        if target.stat().st_size != entry["bytes"]:
            raise ValueError("Completed artifact size changed")
        return []
    gaps = []
    cursor = 0
    for start, end, _path in sources(entry):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = end
    if cursor < entry["bytes"]:
        gaps.append((cursor, entry["bytes"]))
    return gaps


def inventory(plan, ledger):
    records = []
    for entry in plan["files"]:
        gaps = missing(entry)
        records.append(
            {
                "path": entry["path"],
                "expected_bytes": entry["bytes"],
                "missing_bytes": sum(end - start for start, end in gaps),
                "missing_ranges_exclusive_end": gaps,
            }
        )
    accounted = PRIOR_BYTES + sum(row["bytes"] for row in ledger)
    needed = sum(row["missing_bytes"] for row in records)
    result = {
        "accounted_bytes": accounted,
        "remaining_budget_bytes": BUDGET - accounted,
        "exact_missing_payload_bytes": needed,
        "projected_remaining_bytes": BUDGET - accounted - needed,
        "fits_budget": accounted + needed <= BUDGET,
        "connections": 1,
        "stream_buffer_bytes": CHUNK,
        "maximum_http_range_bytes": RANGE,
        "files": records,
    }
    return result


def transfer(entry, start, end, ledger, ledger_path):
    # end is exclusive. No redirects/URLs supplied by a model or HTTP API client.
    folder = VOICE / "artifacts/ranges" / Path(entry["path"]).name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{start}-{end - 1}.part"
    if path.exists():
        raise ValueError("Inventory must account for an existing partial before transfer")
    url = entry["url"]
    headers = {"Range": f"bytes={start}-{end - 1}", "User-Agent": "local-voice-single-stream"}
    row = {
        "url": url,
        "range": [start, end - 1],
        "bytes": 0,
        "kind": "single_stream_range",
        "path": str(path.relative_to(VOICE)),
        "complete": False,
    }
    ledger.append(row)
    save_ledger(ledger_path, ledger)
    sha = hashlib.sha256()
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=30
    ) as response:
        if (
            response.status != 206
            or response.headers.get("Content-Range") != f"bytes {start}-{end - 1}/{entry['bytes']}"
        ):
            # A complete small file may legitimately return 200 to its complete-range request.
            if not (response.status == 200 and start == 0 and end == entry["bytes"]):
                raise ValueError("Origin did not honor the exact validated range")
        with path.open("wb") as output:
            while row["bytes"] < end - start:
                chunk = response.read(min(CHUNK, end - start - row["bytes"]))
                if not chunk:
                    raise ValueError("Truncated range")
                row["bytes"] += len(chunk)
                if PRIOR_BYTES + sum(value["bytes"] for value in ledger) > BUDGET:
                    raise ValueError("Download allowance exceeded")
                # Charge received bytes before writing; a crash cannot undercount persisted bytes.
                save_ledger(ledger_path, ledger)
                output.write(chunk)
                sha.update(chunk)
    row.update(complete=True, sha256=sha.hexdigest())
    save_ledger(ledger_path, ledger)
    path.rename(path.with_suffix(".bin"))


def assemble(entry):
    target = VOICE / entry["path"]
    if target.exists():
        verify(target, entry)
        return
    if missing(entry):
        raise ValueError("Artifact remains incomplete")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_suffix(target.suffix + ".assembled")
    with staging.open("wb") as output:
        for _start, _end, path in sources(entry):
            with path.open("rb") as source:
                while chunk := source.read(CHUNK):
                    output.write(chunk)
    sha = verify(staging, entry)
    staging.replace(target)
    # Retain the original partials as requested. Runtime uses only the verified target.
    print("VERIFIED", entry["path"], sha, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    ledger_path = VOICE / "evidence/inventory-ledger.json"
    ledger = json.loads(ledger_path.read_text())
    plan = json.loads((VOICE / "evidence/download-plan.json").read_text())
    result = inventory(plan, ledger)
    (VOICE / "evidence/single-stream-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}), flush=True)
    if args.inventory_only:
        return
    if not result["fits_budget"]:
        raise SystemExit("Remaining payload exceeds approved allowance")
    for entry in plan["files"]:
        for start, end in missing(entry):
            for offset in range(start, end, RANGE):
                transfer(entry, offset, min(offset + RANGE, end), ledger, ledger_path)
        assemble(entry)
    files = []
    for entry in plan["files"]:
        if entry["path"].startswith("artifacts/"):
            path = VOICE / entry["path"]
            files.append(
                {
                    "path": str(path.relative_to(VOICE / "artifacts")),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                    "source": entry["url"],
                    "revision": entry.get("revision"),
                }
            )
    (VOICE / "artifacts/manifest.json").write_text(json.dumps({"files": files}, indent=2) + "\n")


if __name__ == "__main__":
    main()
