"""One genuine local STT -> explicitly confirmed recall -> TTS HTTP smoke.

Synthetic English source only. Does not establish human/Taglish accuracy or naturalness.
Run only inside voice_guard; refuses to overwrite a previous attempted smoke result.
"""

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
PORT = 18808


def main():
    result_path = OUT / "real-smoke.json"
    if result_path.exists():
        raise SystemExit("Refusing a second smoke over prior evidence")
    result = {
        "passed": False,
        "input_kind": "synthetic eSpeak NG English; not human recognition acceptance",
        "stt_calls": 0,
        "tts_calls": 0,
        "servers_stopped": False,
        "network_scope": "Python server/worker guards, not OS-wide isolation",
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    process = None
    try:
        subprocess.run(
            [
                str(ROOT / "voice/runtime/bin/python"),
                str(ROOT / "scripts/generate_synthetic_voice.py"),
            ],
            check=True,
            timeout=15,
        )
        fixture = (OUT / "synthetic-input.wav").read_bytes()
        with (
            tempfile.TemporaryDirectory(prefix="voice-smoke-data-") as directory,
            (OUT / "real-smoke-server.log").open("w") as log,
        ):
            env = {
                **os.environ,
                "APP_DATA_DIR": directory,
                "APP_PORT": str(PORT),
                "APP_VISION_DISABLED": "1",
                "APP_VOICE_ENABLED": "1",
                "APP_VOICE_TEST_GUARD_54": "1",
                "APP_OFFLINE_AUDIT_LOG": str(OUT / "real-smoke-audit.jsonl"),
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
                    base_url=f"http://127.0.0.1:{PORT}", trust_env=False, timeout=35
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
                        raise RuntimeError("Server startup deadline")
                    client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
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
                    generation = client.get("/api/status").json()["generation"]
                    db = Path(directory) / "items.sqlite"
                    before_hash = hashlib.sha256(db.read_bytes()).hexdigest()
                    before_files = sorted(
                        str(p.relative_to(directory)) for p in Path(directory).rglob("*")
                    )
                    start = time.monotonic()
                    result["stt_calls"] = 1
                    transcription = client.post(
                        "/api/speech/transcribe",
                        json={
                            "request_id": str(uuid4()),
                            "audio": {
                                "content_type": "audio/wav",
                                "data_base64": base64.b64encode(fixture).decode(),
                            },
                            "language_hint": "en",
                        },
                    )
                    result["stt_http_ms"] = round((time.monotonic() - start) * 1000, 2)
                    result["transcription_status"] = transcription.status_code
                    result["transcription"] = transcription.json()
                    result_path.write_text(json.dumps(result, indent=2) + "\n")
                    assert transcription.status_code == 200, transcription.text
                    transcript = transcription.json()["transcript"]
                    assert transcription.json()["transcript_confirmed"] is False
                    assert "blue" in transcript.casefold() and "keys" in transcript.casefold(), (
                        "Synthetic phrase not recognized; do not silently repair acceptance input"
                    )
                    # Deliberate test-operator confirmation of the returned transcript, unchanged.
                    start = time.monotonic()
                    result["tts_calls"] = 1
                    response = client.post(
                        "/api/speech/turns",
                        json={
                            "request_id": str(uuid4()),
                            "utterance": transcript,
                            "transcript_confirmed": True,
                        },
                    )
                    result["recall_tts_http_ms"] = round((time.monotonic() - start) * 1000, 2)
                    result["turn_status"] = response.status_code
                    assert response.status_code == 200, response.text
                    turn = response.json()
                    audio = turn["speech"].pop("audio_base64", None)
                    result["turn"] = turn
                    result_path.write_text(json.dumps(result, indent=2) + "\n")
                    assert (
                        turn["kind"] == "memory" and turn["recall"]["items"][0]["id"] == item["id"]
                    )
                    assert turn["speech"]["status"] == "rendered" and audio, turn["speech"]
                    decoded = base64.b64decode(audio, validate=True)
                    with wave.open(io.BytesIO(decoded), "rb") as wav:
                        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (
                            1,
                            2,
                            24000,
                        )
                        count = wav.getnframes()
                        pcm = wav.readframes(count)
                        assert 0 < count <= 720000 and len(pcm) == count * 2 and any(pcm)
                        result["output_duration_seconds"] = count / 24000
                    (OUT / "spoken-response.wav").write_bytes(decoded)
                    result["output_sha256"] = hashlib.sha256(decoded).hexdigest()
                    assert client.get("/api/status").json()["generation"] == generation
                    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_hash
                    assert (
                        sorted(str(p.relative_to(directory)) for p in Path(directory).rglob("*"))
                        == before_files
                    )
                    result["input_persisted_by_backend"] = False
                    result["memory_unchanged"] = True
                    result["passed"] = True
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
