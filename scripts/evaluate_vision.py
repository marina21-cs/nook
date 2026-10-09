"""Actual pinned NanoDet CPU evaluation on licensed public photos, never downloads."""

import argparse
import asyncio
import io
import json
import resource
import socket
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.config import Settings
from app.evidence_store import EvidenceStore
from app.inference.nanodet import CONFIDENCE, MODEL_FILENAME, MODEL_SHA256, NanoDet
from app.inference.vision import VisionAdapter, verified_model

ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "tests/fixtures/vision"


def percentile(values: list[float], fraction: float) -> float:
    return round(sorted(values)[max(0, int(np.ceil(len(values) * fraction)) - 1)], 2)


def run(output: Path) -> None:
    attempts: list[str] = []

    def deny(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
            attempts.append(event)
            raise OSError("Offline evaluation blocks outbound Python sockets and DNS")

    sys.addaudithook(deny)
    with socket.socket() as probe:
        try:
            probe.connect(("203.0.113.1", 9))
        except OSError:
            pass
        else:
            raise RuntimeError("Offline guard failed")
    assert attempts == ["socket.connect"]
    attempts.clear()
    cases: dict[str, tuple[bytes, str, str]] = {}
    for name in (
        "coffee.png",
        "chelsea.png",
        "keys.jpg",
        "scissors.jpg",
        "scissors-collection.jpg",
    ):
        cases[name] = (
            (PHOTOS / name).read_bytes(),
            "image/png" if name.endswith("png") else "image/jpeg",
            "original public photograph",
        )
    coffee = Image.open(PHOTOS / "coffee.png").convert("RGB")
    scissors = Image.open(PHOTOS / "scissors.jpg").convert("RGB")
    variants = {
        "empty-control": (Image.new("RGB", (320, 240), (128, 128, 128)), "synthetic empty control"),
        "coffee-blurred": (
            coffee.filter(ImageFilter.GaussianBlur(24)),
            "CC0 coffee; Gaussian blur radius 24",
        ),
        "coffee-dark": (
            ImageEnhance.Brightness(coffee).enhance(0.08),
            "CC0 coffee; brightness multiplied by 0.08",
        ),
        "scissors-low-resolution": (scissors.resize((32, 24)), "CC0 scissors; resized to 32x24"),
        "scissors-portrait": (
            scissors.transpose(Image.Transpose.ROTATE_90),
            "CC0 scissors; rotated 90 degrees",
        ),
    }
    for name, (image, description) in variants.items():
        image.thumbnail((2048, 2048))
        variant_buffer = io.BytesIO()
        image.save(variant_buffer, "PNG")
        cases[name] = (variant_buffer.getvalue(), "image/png", description)
    report: dict[str, Any] = {
        "model": MODEL_FILENAME,
        "sha256": MODEL_SHA256,
        "runtime": {
            "opencv-python-headless": "4.13.0.92",
            "numpy": np.__version__,
            "device": "CPU",
            "threads": 2,
            "opencl": False,
        },
        "offline": {
            "guard_self_test_passed": True,
            "scope": "Python socket/DNS denial in supervisor and isolated vision workers; no firewall changes or native syscall trace",
        },
        "quality_sample": "5 public photographs + 5 derived/control cases, not representative user shelf/drawer validation; no threshold tuning or held-out product claim",
        "threshold": CONFIDENCE,
        "nms_iou": 0.6,
        "cases": [],
        "stability": {},
    }
    with tempfile.TemporaryDirectory(prefix="appbuilderhck-vision-eval-") as folder:
        settings = Settings(
            data_dir=Path(folder) / "data",
            vision_model=ROOT / "models" / MODEL_FILENAME,
            vision_sha256=MODEL_SHA256,
        )
        store = EvidenceStore(settings)
        try:
            start = time.perf_counter()
            detector = NanoDet(verified_model(settings.vision_model, MODEL_SHA256))  # type: ignore[arg-type]
            report["model_initialization_ms_runtime_already_imported"] = round(
                (time.perf_counter() - start) * 1000, 2
            )
            sanitized = []
            for name, (encoded, mime, description) in cases.items():
                start = time.perf_counter()
                clean, width, height, _ = store.sanitize(encoded, mime)
                preprocessing = round((time.perf_counter() - start) * 1000, 2)
                rgb = np.asarray(Image.open(io.BytesIO(clean)).convert("RGB"))
                times = []
                for _ in range(3):
                    start = time.perf_counter()
                    candidates = detector.infer(rgb)
                    times.append((time.perf_counter() - start) * 1000)
                thresholds = {
                    str(threshold): [
                        {"category": c["category"], "score": round(c["score"], 4)}
                        for c in detector.infer(rgb, threshold)
                    ]
                    for threshold in (0.2, 0.35, 0.5, 0.7)
                }
                report["cases"].append(
                    {
                        "name": name,
                        "provenance": description,
                        "evidence_size": [width, height],
                        "sanitize_ms": preprocessing,
                        "warm_inference_ms": {
                            "runs": [round(t, 2) for t in times],
                            "median": round(statistics.median(times), 2),
                            "p90": percentile(times, 0.9),
                        },
                        "candidates": candidates,
                        "threshold_comparison_exploratory": thresholds,
                    }
                )
                sanitized.append(clean)
            adapter = VisionAdapter(settings)

            async def stability() -> None:
                latencies = []
                failures = []
                for index in range(20):
                    try:
                        candidates, elapsed = await adapter.suggest(
                            sanitized[index % len(sanitized)], asyncio.Event()
                        )
                        latencies.append(elapsed)
                        assert all(c.model_digest == MODEL_SHA256 for c in candidates)
                    except Exception as error:
                        failures.append({"capture": index + 1, "error_type": type(error).__name__})
                report["stability"] = {
                    "captures": 20,
                    "successes": len(latencies),
                    "failures": failures,
                    "worker_per_request": True,
                    "first_full_worker_request_ms": latencies[0] if latencies else None,
                    "median_full_worker_ms": round(statistics.median(latencies), 2)
                    if latencies
                    else None,
                    "p90_full_worker_ms": percentile(latencies, 0.9) if latencies else None,
                    "runs_ms": latencies,
                    "peak_child_rss_mib_linux": round(
                        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 2
                    ),
                }

            asyncio.run(stability())
        finally:
            store.close()
    report["offline"]["runtime_outbound_python_attempts"] = attempts
    report["passed_runtime_checks"] = not attempts and report["stability"]["successes"] == 20
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"output": str(output), "offline": report["offline"], "stability": report["stability"]}
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
