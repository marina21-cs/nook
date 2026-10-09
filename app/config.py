import os
from dataclasses import dataclass
from pathlib import Path

from app.inference.nanodet import MODEL_FILENAME, MODEL_SHA256

TEXT_MODELS = ("qwen2.5:0.5b", "gemma3:1b")
OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    port: int = 8765
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 24_000_000
    evidence_edge: int = 2048
    max_items: int = 200
    max_drafts: int = 20
    max_evidence_bytes: int = 512 * 1024 * 1024
    draft_ttl_seconds: int = 24 * 3600
    text_model: str | None = None
    model_timeout: float = 15.0
    vision_model: Path | None = None
    vision_sha256: str | None = None
    voice_enabled: bool = False

    def __post_init__(self) -> None:
        if self.text_model is not None and self.text_model not in TEXT_MODELS:
            raise ValueError("Text model must be one of the installed model allowlist.")
        if not 1024 <= self.port <= 65535:
            raise ValueError("Port must be between 1024 and 65535.")
        if (self.vision_model is None) != (self.vision_sha256 is None):
            raise ValueError("A vision model and its verified SHA256 are required together.")
        if self.vision_sha256 and (
            len(self.vision_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.vision_sha256)
        ):
            raise ValueError("Vision SHA256 must be 64 lowercase hexadecimal characters.")

    @property
    def origins(self) -> set[str]:
        return {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}

    @property
    def hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    @classmethod
    def from_env(cls) -> "Settings":
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        model = os.environ.get("APP_VISION_MODEL")
        bundled = Path(__file__).resolve().parents[1] / "models" / MODEL_FILENAME
        digest = os.environ.get("APP_VISION_SHA256") or None
        if os.environ.get("APP_VISION_DISABLED") == "1":
            model, digest = None, None
        elif model is None and bundled.is_file():
            model, digest = str(bundled), MODEL_SHA256
        return cls(
            data_dir=Path(os.environ.get("APP_DATA_DIR", str(base / "appbuilderhck"))),
            port=int(os.environ.get("APP_PORT", "8765")),
            text_model=os.environ.get("APP_TEXT_MODEL") or None,
            vision_model=Path(model) if model else None,
            vision_sha256=digest,
            voice_enabled=os.environ.get("APP_VOICE_ENABLED") == "1",
        )
