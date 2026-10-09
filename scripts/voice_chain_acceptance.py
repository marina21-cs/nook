"""Guarded real voice chain with explicit review/edit, isolated data, one worker.

The verified input is a spoken memory description, not a question. Its unchanged
transcript exercises unknown fallback; a clearly recorded operator edit exercises
known recall. No expected words are supplied to recognition or substituted secretly.
"""

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
FIXTURE = OUT / "kokoro-readback-16k.wav"
FIXTURE_SHA256 = "76da9b0d60504ee41e7c1aa00cbeb0756ec6885961dce94075e2b63021b087d2"


def worker_identity(server_pid):
    children = Path(f"/proc/{server_pid}/task/{server_pid}/children").read_text().split()
    found = []
    for pid in children:
        if "scripts/voice_worker.py" in Path(f"/proc/{pid}/cmdline").read_bytes().decode().replace(
            "\0", " "
        ):
            stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            found.append({"pid": int(pid), "start_ticks": int(stat[19])})
    assert len(found) == 1, f"Expected one persistent worker, got {found}"
    return found[0]


def snapshot(directory, client):
    root = Path(directory)
    return {
        "generation": client.get("/api/status").json()["generation"],
        "files": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        },
    }


def speech_evidence(body, destination):
    encoded = body["speech"].pop("audio_base64", None)
    assert body["speech"]["status"] == "rendered" and encoded, body["speech"]
    data = base64.b64decode(encoded, validate=True)
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 24000)
        count = wav.getnframes()
        pcm = wav.readframes(count)
        assert 0 < count <= 720000 and len(pcm) == count * 2 and any(pcm)
    destination.write_bytes(data)
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(data).hexdigest(),
        "duration_seconds": count / 24000,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        raise ValueError("Invalid evidence name")
    path = OUT / f"{args.name}.json"
    if path.exists():
        raise ValueError("Preserve prior evidence")
    result = {
        "passed": False,
        "stt_requests": 0,
        "tts_requests": 0,
        "servers_stopped": False,
        "input_scope": "verified synthetic Kokoro memory-description fixture; not human/Taglish accuracy",
        "confirmation_scope": "explicit operator review/edit to a lookup label; original transcript also tested unchanged as unknown",
        "network_scope": "Python network guards, not OS-wide isolation",
    }

    def save():
        path.write_text(json.dumps(result, indent=2) + "\n")

    save()
    try:
        data = FIXTURE.read_bytes()
        assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
        result["fixture_sha256"] = FIXTURE_SHA256
        with (
            tempfile.TemporaryDirectory(prefix="voice-chain-") as directory,
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
            result["server_pid"] = process.pid
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
                    response = client.post(
                        "/api/items",
                        json={
                            "confirmed": True,
                            "idempotency_key": str(uuid4()),
                            "personal_name": "blue keys",
                            "location": "Desk drawer",
                        },
                    )
                    assert response.status_code == 201, response.text
                    item = response.json()["items"][0]
                    baseline = snapshot(directory, client)
                    result["baseline"] = baseline
                    chain_start = time.monotonic()
                    start = chain_start
                    result["stt_requests"] = 1
                    save()
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
                    result["stt_http_ms"] = round((time.monotonic() - start) * 1000, 2)
                    result["transcription_status"] = response.status_code
                    result["transcription"] = response.json()
                    save()
                    assert response.status_code == 200, response.text
                    transcript = response.json()["transcript"]
                    assert (
                        response.json()["transcript_confirmed"] is False
                        and response.json()["persisted"] is False
                    )
                    assert snapshot(directory, client) == baseline
                    identity = worker_identity(process.pid)
                    result["worker_after_stt"] = identity
                    result["unconfirmed_transcription_memory_unchanged"] = True
                    # Explicit test-operator edit, outside the recognizer/backend. Never counted
                    # as unchanged recognized-question acceptance or recognition accuracy.
                    reviewed = "blue keys"
                    result["review"] = {
                        "recognized_text": transcript,
                        "reviewed_text": reviewed,
                        "edited": True,
                        "reason": "Fixture is a description; operator requests a lookup by the recognized item label.",
                    }
                    start = time.monotonic()
                    rejections = []
                    for confirmation in [False, None]:
                        payload = {"request_id": str(uuid4()), "utterance": reviewed}
                        if confirmation is not None:
                            payload["transcript_confirmed"] = confirmation
                        rejected = client.post("/api/speech/turns", json=payload)
                        assert rejected.status_code == 422, rejected.text
                        assert snapshot(directory, client) == baseline
                        rejections.append(
                            {"confirmation": confirmation, "status": rejected.status_code}
                        )
                    result["unconfirmed_turn_rejections"] = rejections
                    result["confirmation_rejection_checks_ms"] = round(
                        (time.monotonic() - start) * 1000, 2
                    )
                    assert worker_identity(process.pid) == identity
                    start = time.monotonic()
                    result["tts_requests"] = 1
                    save()
                    response = client.post(
                        "/api/speech/turns",
                        json={
                            "request_id": str(uuid4()),
                            "utterance": reviewed,
                            "transcript_confirmed": True,
                        },
                    )
                    result["confirmed_recall_tts_http_ms"] = round(
                        (time.monotonic() - start) * 1000, 2
                    )
                    result["full_known_chain_ms"] = round(
                        (time.monotonic() - chain_start) * 1000, 2
                    )
                    body = response.json()
                    result["known_status"] = response.status_code
                    assert response.status_code == 200, body
                    assert (
                        body["kind"] == "memory" and body["recall"]["items"][0]["id"] == item["id"]
                    ), body
                    assert body["recall"]["inference_used"] is False
                    result["known_speech"] = speech_evidence(body, OUT / f"{args.name}-known.wav")
                    result["known_response"] = body
                    result["worker_after_known_tts"] = worker_identity(process.pid)
                    assert result["worker_after_known_tts"] == identity
                    assert snapshot(directory, client) == baseline
                    result["known_chain_passed"] = True
                    save()
                    # Confirm the actual unchanged description: unsupported extra query terms
                    # must not be silently reinterpreted as an authoritative item location.
                    start = time.monotonic()
                    result["tts_requests"] = 2
                    save()
                    response = client.post(
                        "/api/speech/turns",
                        json={
                            "request_id": str(uuid4()),
                            "utterance": transcript,
                            "transcript_confirmed": True,
                        },
                    )
                    result["unknown_recall_tts_http_ms"] = round(
                        (time.monotonic() - start) * 1000, 2
                    )
                    body = response.json()
                    result["unknown_status"] = response.status_code
                    assert response.status_code == 200 and body["kind"] == "unknown", body
                    assert body["recall"]["items"] == [] and not body["recall"]["inference_used"], (
                        body
                    )
                    result["unknown_speech"] = speech_evidence(
                        body, OUT / f"{args.name}-unknown.wav"
                    )
                    result["unknown_response"] = body
                    result["worker_after_unknown_tts"] = worker_identity(process.pid)
                    assert result["worker_after_unknown_tts"] == identity
                    assert snapshot(directory, client) == baseline
                    result.update(
                        passed=True,
                        full_chain_with_fallback_ms=round(
                            (time.monotonic() - chain_start) * 1000, 2
                        ),
                        one_persistent_worker=True,
                        memory_unchanged=True,
                        input_persisted_by_backend=False,
                    )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                result["servers_stopped"] = True
                worker = result.get("worker_after_stt")
                result["worker_stopped"] = (
                    worker is None or not Path(f"/proc/{worker['pid']}").exists()
                )
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        save()
        print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
