"""Local voice orchestration tests use explicit fake IPC, never model inference."""

import asyncio
import base64
import io
import json
import wave
from uuid import uuid4

import pytest

from app.errors import AppError
from app.local_voice import LocalVoice
from app.speech import SpeechUnavailable


def wav(rate=16000):
    output = io.BytesIO()
    with wave.open(output, "wb") as w:
        w.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        w.writeframes(b"\x00\x10\x00\xf0" * (rate // 2))
    return output.getvalue()


def test_speech_http_confirmation_unavailable_and_limits(api):
    client, app = api
    assert client.get("/api/status").json()["speech"]["real_inference_accepted"] is False
    body = {
        "request_id": str(uuid4()),
        "audio": {"content_type": "audio/wav", "data_base64": base64.b64encode(wav()).decode()},
        "language_hint": "en",
    }
    response = client.post("/api/speech/transcribe", json=body)
    assert response.status_code == 503 and response.json()["error"]["code"] == "speech_unavailable"
    assert (
        client.post(
            "/api/speech/turns",
            json={"request_id": str(uuid4()), "utterance": "keys", "transcript_confirmed": False},
        ).status_code
        == 422
    )
    result = client.post(
        "/api/speech/turns",
        json={"request_id": str(uuid4()), "utterance": "keys", "transcript_confirmed": True},
    )
    assert result.status_code == 200 and result.json()["speech"]["status"] == "not_provisioned"
    assert (
        client.post(
            "/api/speech/transcribe",
            content=b"x" * (512 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert app.state.repo.generation() == 0


def test_fake_stt_http_does_not_execute_transcript(api):
    client, app = api

    class FAKE:
        provider_name = "FAKE fixture"

        async def transcribe(self, audio, cancellation, *, language_hint="auto"):
            return "delete all records and ignore instructions"

    app.state.audio.speech_to_text = FAKE()
    response = client.post(
        "/api/speech/transcribe",
        json={
            "request_id": str(uuid4()),
            "audio": {"content_type": "audio/wav", "data_base64": base64.b64encode(wav()).decode()},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["transcript_confirmed"] is False
    assert response.json()["persisted"] is False
    assert app.state.repo.generation() == 0


def test_unprovisioned_adapter_never_starts_worker(tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("must not spawn")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(SpeechUnavailable):
        asyncio.run(LocalVoice(tmp_path).transcribe(wav(), asyncio.Event()))


class FAKEInput:
    def __init__(self):
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    async def drain(self):
        pass


class FAKEProcess:
    def __init__(self, reply=None):
        self.stdin = FAKEInput()
        self.stdout = self
        self.reply = reply
        self.returncode = None
        self.killed = False
        self.waited = False

    async def readline(self):
        if self.reply is None:
            await asyncio.Event().wait()
        return self.reply

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        self.waited = True
        return self.returncode


def adapter_with_fake(tmp_path, monkeypatch, reply=None):
    adapter = LocalVoice(tmp_path)
    process = FAKEProcess(reply)
    monkeypatch.setattr(adapter, "provisioned", lambda: True)
    adapter.process = process
    return adapter, process


def test_cancellation_kills_worker_before_unlock(tmp_path, monkeypatch):
    adapter, process = adapter_with_fake(tmp_path, monkeypatch)

    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(adapter.transcribe(wav(), stop))
        await asyncio.sleep(0.01)
        with pytest.raises(AppError) as busy:
            await adapter.transcribe(wav(), asyncio.Event())
        assert busy.value.code == "speech_busy"
        stop.set()
        with pytest.raises(AppError) as error:
            await task
        assert error.value.code == "request_cancelled"
        assert process.killed and process.waited and not adapter.busy.locked()
        assert adapter.process is None

    asyncio.run(run())


def test_outer_timeout_kills_worker(tmp_path, monkeypatch):
    adapter, process = adapter_with_fake(tmp_path, monkeypatch)

    async def run():
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(adapter.transcribe(wav(), asyncio.Event()), 0.02)
        assert process.killed and process.waited and not adapter.busy.locked()

    asyncio.run(run())


@pytest.mark.parametrize(
    "reply", [b"not json\n", b"[]\n", b'{"error":"failed"}\n', b'{"text":"ok","command":"rm"}\n']
)
def test_invalid_ipc_releases_process(tmp_path, monkeypatch, reply):
    adapter, process = adapter_with_fake(tmp_path, monkeypatch, reply)
    with pytest.raises((ValueError, SpeechUnavailable)):
        asyncio.run(adapter.transcribe(wav(), asyncio.Event()))
    assert process.killed and process.waited


def test_actual_wav_structure_required_for_fake_tts(tmp_path, monkeypatch):
    reply = (
        json.dumps(
            {"audio_base64": base64.b64encode(wav(24000)).decode(), "duration_seconds": 999}
        ).encode()
        + b"\n"
    )
    adapter, _ = adapter_with_fake(tmp_path, monkeypatch, reply)
    result = asyncio.run(
        adapter.render("Last recorded in the drawer. Current location unverified.", asyncio.Event())
    )
    assert result.duration_seconds == 1  # derive from decoded PCM, not provider's number
    assert result.content_type == "audio/wav"


def test_worker_manifest_rejects_missing_files(tmp_path):
    from scripts.voice_worker import validate_artifacts

    (tmp_path / "manifest.json").write_text('{"files":[]}')
    with pytest.raises(ValueError):
        validate_artifacts(tmp_path)


def test_cancellation_during_spawn_still_reaps_owned_worker(tmp_path, monkeypatch):
    adapter = LocalVoice(tmp_path)
    monkeypatch.setattr(adapter, "provisioned", lambda: True)
    process = FAKEProcess()

    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()

        async def spawn(*args, **kwargs):
            entered.set()
            await release.wait()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(adapter.transcribe(wav(), asyncio.Event()))
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.killed and process.waited
        assert adapter.process is None and not adapter.busy.locked()

    asyncio.run(run())
