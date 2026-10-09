"""Opt-in local CPU speech process; no installer, network client or user commands."""

import asyncio
import base64
import contextlib
import json
import os
from pathlib import Path
from typing import Any

from app.errors import AppError
from app.speech import RenderedSpeech, SpeechUnavailable
from app.turn_contracts import MAX_SPEECH_BYTES

ROOT = Path(__file__).resolve().parents[1]


class LocalVoice:
    """One shared lazy STT/TTS worker. Cancellation kills it before releasing ownership."""

    provider_name = "local-whisper-tiny"

    def __init__(self, root: Path = ROOT / "voice") -> None:
        self.root = root
        self.busy = asyncio.Lock()
        self.process: asyncio.subprocess.Process | None = None
        self.last_metrics: dict[str, Any] = {}

    def provisioned(self) -> bool:
        return (self.root / "runtime/bin/python").is_file() and (
            self.root / "artifacts/manifest.json"
        ).is_file()

    async def close(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        await process.wait()

    async def _call(self, body: dict, cancellation: asyncio.Event) -> dict:
        if self.busy.locked():
            raise AppError(409, "speech_busy", "One local voice request is already running.")
        async with self.busy:
            if cancellation.is_set():
                raise AppError(409, "request_cancelled", "Speech request cancelled.")
            if not self.provisioned():
                raise SpeechUnavailable("Pinned local speech artifacts are not provisioned.")
            stop = asyncio.create_task(cancellation.wait())
            work = None
            try:
                if self.process is None or self.process.returncode is not None:
                    # Fixed program/arguments, CPU threads, local files and no downloads.
                    env = {
                        **os.environ,
                        "HF_HUB_OFFLINE": "1",
                        "TRANSFORMERS_OFFLINE": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1",
                        "OMP_NUM_THREADS": "2",
                        "MKL_NUM_THREADS": "2",
                        "OPENBLAS_NUM_THREADS": "2",
                        "TOKENIZERS_PARALLELISM": "false",
                        "CUDA_VISIBLE_DEVICES": "",
                    }
                    launch = asyncio.create_task(
                        asyncio.create_subprocess_exec(
                            str(self.root / "runtime/bin/python"),
                            "-I",
                            str(ROOT / "scripts/voice_worker.py"),
                            str(self.root / "artifacts"),
                            env=env,
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                            limit=2 * MAX_SPEECH_BYTES,
                        )
                    )
                    try:
                        self.process = await asyncio.shield(launch)
                    except asyncio.CancelledError:
                        # Own a process created during the cancellation race before cleanup.
                        self.process = await launch
                        raise
                process = self.process
                assert process.stdin is not None and process.stdout is not None
                process.stdin.write(json.dumps(body).encode() + b"\n")
                await process.stdin.drain()
                work = asyncio.create_task(process.stdout.readline())
                done, _ = await asyncio.wait(
                    {work, stop}, timeout=30, return_when=asyncio.FIRST_COMPLETED
                )
                if cancellation.is_set():
                    raise AppError(409, "request_cancelled", "Speech request cancelled.")
                if work not in done:
                    raise TimeoutError("Local speech deadline exceeded")
                raw = work.result()
                if not raw or len(raw) > 2 * MAX_SPEECH_BYTES:
                    raise ValueError("Invalid voice IPC size")
                value = json.loads(raw)
                if not isinstance(value, dict) or value.get("error"):
                    raise SpeechUnavailable("Local speech worker failed or resource gate blocked.")
                if set(value) - {"text", "audio_base64", "duration_seconds", "metrics"}:
                    raise ValueError("Unexpected voice IPC fields")
                metrics = value.get("metrics", {})
                if not isinstance(metrics, dict):
                    raise ValueError("Invalid metrics")
                self.last_metrics = metrics
                return value
            except BaseException:
                # Await process termination even when the request task itself is cancelled.
                cleanup = asyncio.create_task(self.close())
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                raise
            finally:
                stop.cancel()
                if work is not None:
                    work.cancel()
                await asyncio.gather(
                    stop, *([work] if work is not None else []), return_exceptions=True
                )

    async def transcribe(
        self, audio: bytes, cancellation: asyncio.Event, *, language_hint: str = "auto"
    ) -> str:
        from app.audio_contracts import validate_wav

        validate_wav(audio)
        if language_hint not in {"en", "tl", "auto"}:
            raise ValueError("Unsupported language hint")
        value = await self._call(
            {
                "operation": "transcribe",
                "audio_base64": base64.b64encode(audio).decode(),
                "language_hint": language_hint,
            },
            cancellation,
        )
        text = value.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Invalid speech transcript")
        return text.strip()

    async def render(self, text: str, cancellation: asyncio.Event) -> RenderedSpeech:
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 600:
            raise SpeechUnavailable("Reply exceeds bounded local speech length; read the text.")
        value = await self._call({"operation": "render", "text": text}, cancellation)
        audio = base64.b64decode(value.get("audio_base64", ""), validate=True)
        if not 44 < len(audio) <= MAX_SPEECH_BYTES:
            raise ValueError("Invalid rendered audio length")
        import io
        import wave

        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                1,
                2,
                24000,
                "NONE",
            ):
                raise ValueError("Invalid rendered PCM")
            duration = wav.getnframes() / 24000
            if (
                not 0 < duration <= 30
                or len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2
            ):
                raise ValueError("Invalid rendered duration")
        return RenderedSpeech(audio, "audio/wav", duration)
