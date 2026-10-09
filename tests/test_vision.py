"""Real CPU detector checks on explicitly licensed public photos; no fake inference claim."""

import asyncio
import hashlib
import io
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.errors import AppError
from app.inference.nanodet import CONFIDENCE, MODEL_FILENAME, MODEL_SHA256, NanoDet
from app.inference.vision import VisionAdapter, verified_model

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / MODEL_FILENAME
PHOTOS = ROOT / "tests/fixtures/vision"


@pytest.fixture
def detector():
    return NanoDet(verified_model(MODEL, MODEL_SHA256))


def settings(tmp_path, **changes):
    return replace(
        Settings(data_dir=tmp_path / "data", vision_model=MODEL, vision_sha256=MODEL_SHA256),
        **changes,
    )


def test_approved_model_default_can_be_disabled(tmp_path, monkeypatch):
    for name in ("APP_VISION_MODEL", "APP_VISION_SHA256", "APP_VISION_DISABLED"):
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env().vision_sha256 == MODEL_SHA256
    monkeypatch.setenv("APP_VISION_DISABLED", "1")
    assert Settings.from_env().vision_model is None


def test_missing_unsupported_and_symlink_models(tmp_path):
    missing = VisionAdapter(settings(tmp_path, vision_model=tmp_path / "missing.onnx"))
    assert missing.state == "invalid_model_file"
    arbitrary = tmp_path / "unreviewed.onnx"
    arbitrary.write_bytes(b"not approved ONNX weights")
    digest = hashlib.sha256(arbitrary.read_bytes()).hexdigest()
    assert (
        VisionAdapter(settings(tmp_path, vision_model=arbitrary, vision_sha256=digest)).state
        == "unsupported_model"
    )
    link = tmp_path / "linked.onnx"
    link.symlink_to(MODEL)
    assert VisionAdapter(settings(tmp_path, vision_model=link)).state == "invalid_model_file"


@pytest.mark.parametrize("size", [(600, 400), (400, 600), (416, 416), (2048, 1)])
def test_letterbox_and_normalized_coordinate_contract(detector, size):
    width, height = size
    padded, (top, left, new_h, new_w) = detector.letterbox(
        np.full((height, width, 3), [240, 20, 10], dtype=np.uint8)
    )
    assert padded.shape == (416, 416, 3)
    assert new_h >= 1 and new_w >= 1
    assert padded[top, left].tolist() == [240, 20, 10]  # RGB, no channel reversal.
    assert np.count_nonzero(padded[:top]) == 0
    mapped = detector.map_region(
        np.array([left + new_w / 4, top + new_h / 4, left + 3 * new_w / 4, top + 3 * new_h / 4]),
        (top, left, new_h, new_w),
        size,
    )
    if height == 1:
        assert mapped is None  # Subpixel region is unusable in the original evidence.
    else:
        assert mapped == pytest.approx({"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5})
    assert detector.map_region(
        np.array([-100, -100, 600, 600]), (top, left, new_h, new_w), size
    ) == {"x": 0, "y": 0, "w": 1, "h": 1}
    assert (
        detector.map_region(np.array([-20, -20, -1, -1]), (top, left, new_h, new_w), size) is None
    )


@pytest.mark.parametrize("corruption", ["count", "shape", "nonfinite", "score"])
def test_invalid_detector_tensors_are_rejected(detector, corruption):
    tensors = []
    for anchors in detector.anchors:
        tensors.extend([np.zeros((1, len(anchors), 80)), np.zeros((1, len(anchors), 32))])
    if corruption == "count":
        tensors.pop()
    elif corruption == "shape":
        tensors[0] = np.zeros((80, 1, len(detector.anchors[0])))
    elif corruption == "nonfinite":
        tensors[1][0, 0, 0] = np.inf
    else:
        tensors[0][0, 0, 0] = 1.5
    with pytest.raises(ValueError):
        detector.decode(tensors, CONFIDENCE)


def test_real_cpu_cup_and_no_detection_control(detector):
    rgb = np.asarray(Image.open(PHOTOS / "coffee.png").convert("RGB"))
    candidates = detector.infer(rgb)
    assert any(c["category"] == "cup" for c in candidates)
    assert len(candidates) <= 20
    for candidate in candidates:
        x, y, w, h = (candidate["region"][key] for key in ("x", "y", "w", "h"))
        assert 0 <= x < x + w <= 1 and 0 <= y < y + h <= 1
        assert candidate["score"] >= CONFIDENCE
    assert detector.infer(np.full((240, 320, 3), 128, dtype=np.uint8)) == []


def test_real_worker_verifies_and_rechecks_model(tmp_path):
    local = tmp_path / "model.onnx"
    local.write_bytes(MODEL.read_bytes())
    adapter = VisionAdapter(settings(tmp_path, vision_model=local))
    assert adapter.status()["available"] and not adapter.status()["inference_verified"]
    candidates, elapsed = asyncio.run(
        adapter.suggest((PHOTOS / "coffee.png").read_bytes(), asyncio.Event())
    )
    assert any(c.category == "cup" and c.model_digest == MODEL_SHA256 for c in candidates)
    assert elapsed > 0 and adapter.status()["inference_verified"]
    local.write_bytes(b"changed after startup")
    with pytest.raises(AppError) as error:
        asyncio.run(adapter.suggest((PHOTOS / "coffee.png").read_bytes(), asyncio.Event()))
    assert error.value.code == "vision_failed"


def test_real_worker_timeout_and_cancellation(tmp_path):
    encoded = io.BytesIO()
    Image.new("RGB", (300, 200), "gray").save(encoded, "JPEG")
    adapter = VisionAdapter(settings(tmp_path, model_timeout=0.001))
    with pytest.raises(AppError) as error:
        asyncio.run(adapter.suggest(encoded.getvalue(), asyncio.Event()))
    assert error.value.code == "vision_timeout"
    cancelled = asyncio.Event()
    cancelled.set()
    adapter = VisionAdapter(settings(tmp_path))
    with pytest.raises(AppError) as error:
        asyncio.run(adapter.suggest(encoded.getvalue(), cancelled))
    assert error.value.code == "request_cancelled"
    assert not adapter.status()["inference_verified"]


def test_incompatible_or_absent_runtime_is_manual_available(tmp_path, monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.0.0")
    assert VisionAdapter(settings(tmp_path)).state == "incompatible_runtime"

    def absent(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", absent)
    adapter = VisionAdapter(settings(tmp_path))
    assert adapter.state == "runtime_or_model_missing"
    assert adapter.status()["manual_confirmation_available"]


def test_worker_output_cannot_invent_category_provenance_or_actions(tmp_path, monkeypatch):
    """IPC test double only; these fabricated outputs never count as vision evidence."""
    import multiprocessing

    candidate = {
        "id": str(uuid4()),
        "category": "keys",
        "score": 0.9,
        "region": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
        "model": "fake identity model",
        "model_digest": MODEL_SHA256,
    }

    class Pipe:
        def poll(self):
            return True

        def recv(self):
            return {"candidates": [candidate]}

        def close(self):
            pass

    class Process:
        pid = None

        def start(self):
            pass

    class Context:
        def Pipe(self, **kwargs):
            return Pipe(), Pipe()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(multiprocessing, "get_context", lambda mode: Context())
    adapter = VisionAdapter(settings(tmp_path))
    with pytest.raises(AppError) as error:
        asyncio.run(adapter.suggest(b"IPC test double; not a photo", asyncio.Event()))
    assert error.value.code == "invalid_vision_output"
    assert not adapter.status()["inference_verified"]
