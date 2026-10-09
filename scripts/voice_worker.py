"""Fixed local CPU voice worker. Unprovisioned until pinned manifest/artifacts exist.

No runtime download or installation. Python network guard is not OS-wide isolation.
Input/output remains in pipes and memory. Never run model acceptance without the
separate timestamped CPU/RAM/swap monitor and retained experimental limits.
"""

import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import time
import wave
from pathlib import Path


def deny_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto"}:
        raise OSError("Voice worker network disabled")


def validate_artifacts(root):
    manifest = json.loads((root / "manifest.json").read_text())
    required = {
        "kokoro/config.json",
        "kokoro/kokoro-v1_0.pth",
        "kokoro/af_heart.pt",
        "whisper/model.safetensors",
        "whisper/config.json",
        "whisper/preprocessor_config.json",
        "whisper/tokenizer.json",
        "whisper/tokenizer_config.json",
        "whisper/generation_config.json",
    }
    files = manifest["files"]
    if not isinstance(files, list) or not required <= {f["path"] for f in files}:
        raise ValueError("Incomplete speech manifest")
    for entry in files:
        path = root / entry["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Unsafe artifact path")
        if path.stat().st_size != entry["bytes"]:
            raise ValueError("Artifact size mismatch")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != entry["sha256"]:
            raise ValueError("Artifact digest mismatch")


def resource_gate():
    # Existing unprivileged experimental limits. No sensor/fan/governor changes.
    temps = {}
    for sensor in Path("/sys/class/hwmon").glob("hwmon*"):
        name = (sensor / "name").read_text().strip()
        if name in {"k10temp", "spd5118"}:
            temps.setdefault(name, []).extend(
                float(p.read_text()) / 1000 for p in sensor.glob("temp*_input")
            )
    if not temps.get("k10temp") or not temps.get("spd5118"):
        raise RuntimeError("Required sensors unavailable")
    dimm_limit = 54 if os.environ.get("APP_VOICE_TEST_GUARD_54") == "1" else 52
    if max(temps["k10temp"]) >= 75 or max(temps["spd5118"]) >= dimm_limit:
        raise RuntimeError("Retained resource gate blocked")
    mem = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    if mem["MemAvailable"] < 2 * 1024**3:
        raise RuntimeError("Low available RAM")


def run(root):
    sys.addaudithook(deny_network)
    validate_artifacts(root)
    whisper = processor = pipeline = None
    for raw in sys.stdin.buffer:
        if len(raw) > 500000:
            raise ValueError("Oversized speech request")
        try:
            resource_gate()
            started = time.monotonic()
            body = json.loads(raw)
            with contextlib.redirect_stdout(sys.stderr):
                import numpy as np
                import torch

                torch.set_num_threads(2)
                if body["operation"] == "transcribe":
                    from transformers import WhisperForConditionalGeneration, WhisperProcessor

                    cold = whisper is None
                    if cold:
                        processor = WhisperProcessor.from_pretrained(
                            str(root / "whisper"), local_files_only=True
                        )
                        whisper = WhisperForConditionalGeneration.from_pretrained(
                            str(root / "whisper"), local_files_only=True
                        ).eval()
                    data = base64.b64decode(body["audio_base64"], validate=True)
                    with wave.open(io.BytesIO(data), "rb") as wav:
                        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (
                            1,
                            2,
                            16000,
                        ) or not 0 < wav.getnframes() <= 160000:
                            raise ValueError("Invalid WAV")
                        samples = (
                            np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(
                                np.float32
                            )
                            / 32768
                        )
                    features = processor(
                        samples, sampling_rate=16000, return_tensors="pt"
                    ).input_features
                    hint = body.get("language_hint", "auto")
                    if hint not in {"en", "tl", "auto"}:
                        raise ValueError("Invalid language")
                    with torch.inference_mode():
                        tokens = whisper.generate(
                            features,
                            max_new_tokens=128,
                            do_sample=False,
                            task="transcribe",
                            language=None if hint == "auto" else hint,
                        )
                    result = {
                        "text": processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
                    }
                elif body["operation"] == "render":
                    from kokoro import KModel, KPipeline

                    text = body["text"]
                    if not isinstance(text, str) or not 1 <= len(text) <= 600:
                        raise ValueError("Invalid text")
                    cold = pipeline is None
                    if cold:
                        # Package/model absence fails; no lazy downloader is permitted by the network guard.
                        import spacy

                        spacy.load("en_core_web_sm")
                        model = (
                            KModel(
                                repo_id="hexgrad/Kokoro-82M",
                                config=str(root / "kokoro/config.json"),
                                model=str(root / "kokoro/kokoro-v1_0.pth"),
                            )
                            .to("cpu")
                            .eval()
                        )
                        pipeline = KPipeline(
                            lang_code="a", model=model, device="cpu", repo_id="hexgrad/Kokoro-82M"
                        )
                    chunks = []
                    count = 0
                    for chunk in pipeline(text, voice=str(root / "kokoro/af_heart.pt"), speed=1):
                        audio = chunk.audio.detach().cpu().numpy()
                        count += len(audio)
                        if count > 30 * 24000:
                            raise ValueError("Speech exceeds duration bound")
                        chunks.append(audio)
                    if not chunks:
                        raise ValueError("Empty synthesis")
                    samples = np.concatenate(chunks)
                    if not np.isfinite(samples).all():
                        raise ValueError("Nonfinite synthesis")
                    output = io.BytesIO()
                    with wave.open(output, "wb") as wav:
                        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                        wav.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
                    result = {
                        "audio_base64": base64.b64encode(output.getvalue()).decode(),
                        "duration_seconds": len(samples) / 24000,
                    }
                else:
                    raise ValueError("Unknown operation")
            result["metrics"] = {
                "cold": cold,
                "whole_call_ms": round((time.monotonic() - started) * 1000, 2),
            }
            print(json.dumps(result), flush=True)
        except Exception:
            print(json.dumps({"error": "speech_unavailable"}), flush=True)
            return


if __name__ == "__main__":
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        run(Path(sys.argv[1]))
    except Exception:
        print(json.dumps({"error": "speech_unavailable"}), flush=True)
