import asyncio
import hashlib
import importlib.metadata
import io
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.contracts import Candidate
from app.errors import AppError
from app.inference.nanodet import (
    CLASSES,
    CONFIDENCE,
    MODEL_BYTES,
    MODEL_ID,
    MODEL_SHA256,
    NMS_IOU,
    NUMPY_VERSION,
    OPENCV_VERSION,
)


def verified_model(path: Path, expected_digest: str | None) -> bytes:
    """Read once without following links; only the approved official model can run."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as file:
        if os.fstat(file.fileno()).st_size != MODEL_BYTES:
            raise ValueError("Invalid model size")
        data = file.read(MODEL_BYTES + 1)
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != MODEL_BYTES or digest != expected_digest or digest != MODEL_SHA256:
        raise ValueError("Unapproved or changed model")
    return data


def deny_worker_network(event: str, args: tuple) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
        raise OSError("Vision worker has no network permission")


def detect_worker(pipe: Any, model_path: str, digest: str, encoded: bytes) -> None:
    """Isolated CPU image task with no Python socket/DNS access, camera or downloads."""
    try:
        sys.addaudithook(deny_worker_network)
        import numpy as np
        from PIL import Image

        from app.inference.nanodet import NanoDet

        with Image.open(io.BytesIO(encoded)) as image:
            array = np.asarray(image.convert("RGB"))
        detector = NanoDet(verified_model(Path(model_path), digest))
        output = detector.infer(array)
        candidates = []
        for detection in output:
            candidates.append(
                {
                    "id": str(uuid4()),
                    **detection,
                    "model": MODEL_ID,
                    "model_digest": digest,
                }
            )
        pipe.send({"candidates": candidates})
    except Exception:
        pipe.send(
            {"error": "vision_failed"}
        )  # No photo text, paths or stack trace leaves the worker.
    finally:
        pipe.close()


class VisionAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.busy = asyncio.Lock()
        self.last_verified_inference = False
        self.digest: str | None = None
        self.state = "not_configured"
        self.runtime_version: str | None = None
        if settings.vision_model:
            try:
                path: Path = settings.vision_model
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or path.stat().st_size > 32 * 1024 * 1024
                ):
                    self.state = "invalid_model_file"
                    return
                self.digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if self.digest != settings.vision_sha256:
                    self.state = "checksum_mismatch"
                    return
                if self.digest != MODEL_SHA256 or path.stat().st_size != MODEL_BYTES:
                    self.state = "unsupported_model"
                    return
                verified_model(path, self.settings.vision_sha256)
                self.runtime_version = importlib.metadata.version("opencv-python-headless")
                numpy_version = importlib.metadata.version("numpy")
                if self.runtime_version != OPENCV_VERSION or numpy_version != NUMPY_VERSION:
                    self.state = "incompatible_runtime"
                    return
                self.state = "configured_unvalidated"
            except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
                self.state = "runtime_or_model_missing"

    def status(self) -> dict:
        return {
            "available": self.state == "configured_unvalidated",
            "state": self.state,
            "model": MODEL_ID if self.settings.vision_model else None,
            "model_digest": self.digest,
            "runtime_version": self.runtime_version,
            "delegate": "CPU",
            "mode": "IMAGE",
            "inference_verified": self.last_verified_inference,
            "manual_confirmation_available": True,
            "downloads_automatic": False,
            "input_size": [416, 416],
            "score_threshold": CONFIDENCE,
            "nms_iou_threshold": NMS_IOU,
            "max_candidates": 20,
            "supported_categories": list(CLASSES),
            "unsupported_examples": ["keys", "chargers", "wallets", "eyeglasses"],
            "personal_identity_supported": False,
            "python_worker_network_blocked": True,
        }

    async def suggest(
        self, encoded: bytes, cancelled: asyncio.Event
    ) -> tuple[list[Candidate], float]:
        if self.state != "configured_unvalidated":
            raise AppError(
                503,
                "vision_unavailable",
                "Local vision is unavailable. Review the photo and enter items manually.",
                stage=self.state,
                manual_confirmation_available=True,
            )
        if self.busy.locked():
            raise AppError(
                503, "vision_busy", "Another photo is being checked. Retry or label manually."
            )
        async with self.busy:
            start = time.monotonic()
            context = multiprocessing.get_context("spawn")
            receive, send = context.Pipe(duplex=False)
            process = context.Process(
                target=detect_worker,
                args=(send, str(self.settings.vision_model), self.digest, encoded),
                daemon=True,
            )
            try:
                process.start()
                send.close()
                while not receive.poll():
                    if cancelled.is_set():
                        raise AppError(
                            409, "request_cancelled", "Photo check cancelled; result discarded."
                        )
                    if time.monotonic() - start > self.settings.model_timeout:
                        raise AppError(
                            504,
                            "vision_timeout",
                            "Local photo check timed out. Draft is preserved; retry or label manually.",
                        )
                    if not process.is_alive():
                        raise AppError(
                            503, "vision_failed", "Vision worker stopped. Draft is preserved."
                        )
                    await asyncio.sleep(0.02)
                payload = receive.recv()
                if cancelled.is_set():
                    raise AppError(
                        409, "request_cancelled", "Photo check cancelled; result discarded."
                    )
                if "error" in payload:
                    raise AppError(
                        503,
                        "vision_failed",
                        "Local vision failed. Draft is preserved; retry or label manually.",
                    )
                raw = payload["candidates"]
                if not isinstance(raw, list) or len(raw) > 20:
                    raise ValueError("Invalid candidate count")
                candidates = [Candidate.model_validate_json(json.dumps(c)) for c in raw]
                if any(
                    c.category not in CLASSES
                    or c.model != MODEL_ID
                    or c.model_digest != MODEL_SHA256
                    or c.score < CONFIDENCE
                    for c in candidates
                ):
                    raise ValueError("Untrusted candidate provenance or category")
                self.last_verified_inference = True
                return candidates, round((time.monotonic() - start) * 1000, 2)
            except AppError:
                raise
            except Exception as exc:
                raise AppError(
                    503,
                    "invalid_vision_output",
                    "Local detector output failed validation. Label manually.",
                ) from exc
            finally:
                if process.pid is not None and process.is_alive():
                    process.terminate()
                if process.pid is not None:
                    process.join(timeout=0.5)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=0.5)
                receive.close()
                send.close()
