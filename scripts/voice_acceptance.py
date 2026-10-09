"""Separate bounded real STT/TTS HTTP checks; synthetic fixtures, no accuracy sweep."""

import argparse
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "voice/evidence"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["stt", "tts"], required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--audio", type=Path)
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        raise ValueError("Invalid evidence name")
    result_path = OUT / f"{args.name}.json"
    if result_path.exists():
        raise ValueError("Preserve prior evidence")
    result = dict(
        mode=args.mode,
        passed=False,
        stt_calls=0,
        tts_requests=0,
        servers_stopped=False,
        scope="Real localhost; Python network guard, not OS-wide isolation; no human/naturalness acceptance",
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    process = None
    try:
        with (
            tempfile.TemporaryDirectory(prefix="voice-independent-") as directory,
            (OUT / f"{args.name}-server.log").open("w") as log,
        ):
            env = {
                **os.environ,
                "APP_DATA_DIR": directory,
                "APP_PORT": "18808",
                "APP_VISION_DISABLED": "1",
                "APP_VOICE_ENABLED": "1",
                "APP_VOICE_TEST_GUARD_54": "1",
                "APP_OFFLINE_AUDIT_LOG": str(OUT / f"{args.name}-audit.jsonl"),
            }
            env.pop("APP_TEXT_MODEL", None)
            process = subprocess.Popen(
                [sys.executable, "-m", "scripts.offline_server"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                with httpx.Client(
                    base_url="http://127.0.0.1:18808", trust_env=False, timeout=35
                ) as client:
                    for _ in range(60):
                        if process.poll() is not None:
                            raise RuntimeError("Server exited")
                        try:
                            if client.get("/api/status").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("Startup deadline")
                    client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
                    if args.mode == "tts":
                        saved = client.post(
                            "/api/items",
                            json={
                                "confirmed": True,
                                "idempotency_key": str(uuid4()),
                                "personal_name": "blue keys",
                                "location": "Desk drawer",
                            },
                        )
                        assert saved.status_code == 201, saved.text
                        item = saved.json()["items"][0]
                    db = Path(directory) / "items.sqlite"
                    before = hashlib.sha256(db.read_bytes()).hexdigest()
                    files = sorted(
                        str(p.relative_to(directory)) for p in Path(directory).rglob("*")
                    )
                    start = time.monotonic()
                    if args.mode == "stt":
                        if args.audio is None:
                            raise ValueError("STT requires explicit audio fixture")
                        data = args.audio.read_bytes()
                        result.update(
                            stt_calls=1,
                            input_sha256=hashlib.sha256(data).hexdigest(),
                            input_path=str(args.audio),
                        )
                        response = client.post(
                            "/api/speech/transcribe",
                            json={
                                "request_id": str(uuid4()),
                                "audio": {
                                    "content_type": "audio/wav",
                                    "data_base64": base64.b64encode(data).decode(),
                                },
                                "language_hint": "en",
                            },
                        )
                    else:
                        result.update(
                            tts_requests=1,
                            input_kind="explicitly confirmed typed text; independent of STT result",
                        )
                        response = client.post(
                            "/api/speech/turns",
                            json={
                                "request_id": str(uuid4()),
                                "utterance": "Where are my blue keys?",
                                "transcript_confirmed": True,
                            },
                        )
                    result.update(
                        http_ms=round((time.monotonic() - start) * 1000, 2),
                        http_status=response.status_code,
                    )
                    body = response.json()
                    if args.mode == "tts":
                        encoded = body.get("speech", {}).pop("audio_base64", None)
                        result["response"] = body
                        assert response.status_code == 200, body
                        assert (
                            body["kind"] == "memory"
                            and body["recall"]["items"][0]["id"] == item["id"]
                        ), body
                        assert body["speech"]["status"] == "rendered" and encoded, body
                        audio = base64.b64decode(encoded, validate=True)
                        with wave.open(io.BytesIO(audio), "rb") as wav:
                            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (
                                1,
                                2,
                                24000,
                            )
                            frames = wav.getnframes()
                            pcm = wav.readframes(frames)
                            assert 0 < frames <= 720000 and len(pcm) == frames * 2 and any(pcm)
                            result["duration_seconds"] = frames / 24000
                        (OUT / f"{args.name}.wav").write_bytes(audio)
                        result["audio_sha256"] = hashlib.sha256(audio).hexdigest()
                    else:
                        result["response"] = body
                        assert response.status_code == 200, body
                        assert body["transcript_confirmed"] is False and body["persisted"] is False
                        result["recognition_evaluated_separately"] = True
                    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
                    assert (
                        sorted(str(p.relative_to(directory)) for p in Path(directory).rglob("*"))
                        == files
                    )
                    result.update(
                        memory_unchanged=True, input_persisted_by_backend=False, passed=True
                    )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                result["servers_stopped"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
