"""Frozen-label held-out challenge evaluation; local fixtures only, no downloads/tuning."""

import argparse
import asyncio
import hashlib
import io
import json
import socket
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.config import Settings
from app.evidence_store import EvidenceStore
from app.inference.nanodet import MODEL_FILENAME, MODEL_SHA256
from app.inference.vision import VisionAdapter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/vision/heldout-20261009"


def iou(box: list[float], region: dict[str, float]) -> float:
    x1, y1, x2, y2 = box
    a, b, c, d = region["x"], region["y"], region["w"], region["h"]
    intersection = max(0, min(x2, a + c) - max(x1, a)) * max(0, min(y2, b + d) - max(y1, b))
    union = (x2 - x1) * (y2 - y1) + c * d - intersection
    return intersection / union if union else 0


def metrics(case: dict, candidates: list[dict]) -> dict:
    targets = case["targets"]
    matched: set[int] = set()
    duplicate = false_positive = context = localization = 0
    for candidate in sorted(candidates, key=lambda c: -c["score"]):
        overlaps = [
            (iou(t["box"], candidate["region"]), n)
            for n, t in enumerate(targets)
            if candidate["category"] == t["category"]
        ]
        score, target = max(overlaps, default=(0, -1))
        if score >= 0.5:
            if target in matched:
                duplicate += 1
            else:
                matched.add(target)
        elif candidate["category"] in case["context_categories"]:
            context += 1
        elif score > 0:
            localization += 1
        else:
            false_positive += 1
    return {
        "expected_supported_targets": len(targets),
        "matched_targets": len(matched),
        "missed_targets": len(targets) - len(matched),
        "duplicate_boxes": duplicate,
        "false_positive_boxes": false_positive,
        "localization_failure_boxes": localization,
        "excluded_context_boxes": context,
        "candidate_count": len(candidates),
    }


async def evaluate(output: Path) -> None:
    expectation_bytes = (FIXTURES / "expected.json").read_bytes()
    expected = json.loads(expectation_bytes)
    assert expected["score_threshold"] == 0.35 and expected["model_sha256"] == MODEL_SHA256
    attempts = []

    def deny(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
            attempts.append(event)
            raise OSError("QA evaluation denies outbound Python socket/DNS calls")

    sys.addaudithook(deny)
    with socket.socket() as probe:
        try:
            probe.connect(("203.0.113.1", 9))
        except OSError:
            pass
        else:
            raise RuntimeError("Guard self-test failed")
    assert attempts == ["socket.connect"]
    attempts.clear()
    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    with tempfile.TemporaryDirectory(prefix="appbuilderhck-heldout-qa-") as folder:
        settings = Settings(
            data_dir=Path(folder),
            vision_model=ROOT / "models" / MODEL_FILENAME,
            vision_sha256=MODEL_SHA256,
        )
        store = EvidenceStore(settings)
        adapter = VisionAdapter(settings)
        try:
            for case in expected["cases"]:
                if "file" in case:
                    raw = (FIXTURES / case["file"]).read_bytes()
                    assert hashlib.sha256(raw).hexdigest() == case["original_sha256"]
                    with Image.open(io.BytesIO(raw)) as source:
                        image = ImageOps.exif_transpose(source).convert("RGB")
                else:
                    image = Image.new("RGB", (320, 240), tuple(case["synthetic_color"]))
                transform = case.get("transform", {})
                if "crop" in transform:
                    w, h = image.size
                    a, b, c, d = transform["crop"]
                    image = image.crop((round(a * w), round(b * h), round(c * w), round(d * h)))
                if "resize" in transform:
                    image = image.resize(tuple(transform["resize"]))
                if "blur" in transform:
                    image = image.filter(ImageFilter.GaussianBlur(transform["blur"]))
                if "brightness" in transform:
                    image = ImageEnhance.Brightness(image).enhance(transform["brightness"])
                # PNG intermediate has no EXIF; app still performs its normal JPEG sanitation.
                image.thumbnail((2048, 2048))
                buffer = io.BytesIO()
                image.save(buffer, "PNG")
                start = time.perf_counter()
                clean, width, height, _ = store.sanitize(buffer.getvalue(), "image/png")
                preprocessing = round((time.perf_counter() - start) * 1000, 2)
                runs: list[dict[str, Any]] = []
                for repetition in range(expected["repetitions"]):
                    candidates, elapsed = await adapter.suggest(clean, asyncio.Event())
                    rows = [c.model_dump(mode="json", exclude={"id"}) for c in candidates]
                    runs.append(
                        {"repeat": repetition + 1, "elapsed_ms": elapsed, "candidates": rows}
                    )
                    latencies.append(elapsed)
                signatures = [json.dumps(r["candidates"], sort_keys=True) for r in runs]
                result = {
                    "name": case["name"],
                    "source_sha256": case.get("original_sha256"),
                    "evidence_size": [width, height],
                    "sanitize_ms": preprocessing,
                    "unknown_acceptable": case["unknown_acceptable"],
                    "repeatable_ignoring_random_candidate_ids": len(set(signatures)) == 1,
                    "metrics_first_run": metrics(case, runs[0]["candidates"]),
                    "worker_latency_ms_median": round(
                        statistics.median(r["elapsed_ms"] for r in runs), 2
                    ),
                    "runs": runs,
                }
                results.append(result)
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in ("name", "metrics_first_run", "worker_latency_ms_median")
                        }
                    ),
                    flush=True,
                )
        finally:
            store.close()
    totals = {
        key: sum(r["metrics_first_run"][key] for r in results)
        for key in results[0]["metrics_first_run"]
    }
    report = {
        "expected_manifest_sha256": hashlib.sha256(expectation_bytes).hexdigest(),
        "frozen_at_utc": expected["frozen_at_utc"],
        "method": expected["method"],
        "model_sha256": MODEL_SHA256,
        "threshold": 0.35,
        "nms_iou": 0.6,
        "new_original_photos": 6,
        "derived_stress_cases": 8,
        "synthetic_empty_controls": 2,
        "full_worker_requests": len(latencies),
        "worker_errors": 0,
        "repeatable_cases": sum(r["repeatable_ignoring_random_candidate_ids"] for r in results),
        "totals_first_run": totals,
        "latency_ms": {
            "median": round(statistics.median(latencies), 2),
            "p90": sorted(latencies)[int(len(latencies) * 0.9)],
            "min": min(latencies),
            "max": max(latencies),
        },
        "offline_guard_self_test_passed": True,
        "runtime_outbound_python_attempts": attempts,
        "network_scope": "Python supervisor socket audit and vision worker denial only; native/syscall, UDP and OS-wide network isolation unproven",
        "cases": results,
    }
    assert not attempts and report["repeatable_cases"] == len(results)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(evaluate(parser.parse_args().output))
