import fcntl
import hashlib
import io
import os
import re
import warnings
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.errors import AppError

ASSET = re.compile(r"^[0-9a-f-]{36}\.(jpg|part)$")
MARKER = "appbuilderhck-local-evidence-v1\n"


class EvidenceStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.data_dir.absolute()
        if self.root.is_symlink():
            raise AppError(503, "unsafe_storage", "Data directory cannot be a symlink.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.root / ".appbuilderhck-owned"
        if not marker.exists():
            if any(self.root.iterdir()):
                raise AppError(503, "unowned_storage", "Choose an empty app-only data directory.")
            self.write_private(marker, MARKER.encode())
        if marker.is_symlink() or marker.read_text() != MARKER:
            raise AppError(503, "unowned_storage", "Data directory ownership marker is invalid.")
        self.root.chmod(0o700)
        self.drafts = self.root / "drafts"
        self.photos = self.root / "photos"
        for path in (self.drafts, self.photos):
            if path.is_symlink():
                raise AppError(503, "unsafe_storage", "Evidence directory cannot be a symlink.")
            path.mkdir(exist_ok=True, mode=0o700)
            path.chmod(0o700)
        fd = os.open(self.root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.lock_file = os.fdopen(fd, "w")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock_file.close()
            raise AppError(
                503, "storage_busy", "Run only one backend process per data directory."
            ) from exc

    def close(self) -> None:
        self.lock_file.close()

    @staticmethod
    def sync_dir(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def write_private(path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        EvidenceStore.sync_dir(path.parent)

    def path(self, item_id: str, draft: bool = False) -> Path:
        key = str(UUID(item_id))
        return (self.drafts if draft else self.photos) / f"{key}.jpg"

    def read(self, item_id: str, draft: bool = False) -> bytes:
        try:
            fd = os.open(self.path(item_id, draft), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as file:
                return file.read(self.settings.max_upload_bytes + 1)
        except OSError as exc:
            raise AppError(404, "evidence_unavailable", "Photo evidence is unavailable.") from exc

    def available(self, item_id: str) -> bool:
        path = self.path(item_id)
        return path.is_file() and not path.is_symlink()

    def remove(self, item_id: str, draft: bool = False) -> None:
        self.path(item_id, draft).unlink(missing_ok=True)  # Unlinks symlinks; never follows them.
        self.sync_dir(self.drafts if draft else self.photos)

    def sanitize(self, data: bytes, content_type: str) -> tuple[bytes, int, int, str]:
        formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
        if content_type not in formats:
            raise AppError(415, "unsupported_image", "Use a JPEG, PNG or still WebP image.")
        if not data or len(data) > self.settings.max_upload_bytes:
            raise AppError(413, "upload_limit", "Photo must be nonempty and at most 10 MiB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != formats[content_type]:
                        raise AppError(
                            415, "type_mismatch", "Image bytes do not match Content-Type."
                        )
                    if getattr(image, "n_frames", 1) != 1:
                        raise AppError(
                            415, "animated_image", "Only a single still image is supported."
                        )
                    if image.width * image.height > self.settings.max_pixels:
                        raise AppError(413, "pixel_limit", "Decoded image exceeds 24 megapixels.")
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    oriented = ImageOps.exif_transpose(image)
                    oriented.thumbnail((self.settings.evidence_edge,) * 2, Image.Resampling.LANCZOS)
                    # Fresh image has no EXIF, ICC, text chunks, GPS or original filename.
                    rgba = oriented.convert("RGBA")
                    clean = Image.new("RGB", rgba.size, "white")
                    clean.paste(rgba, mask=rgba.getchannel("A"))
                    result = io.BytesIO()
                    clean.save(result, "JPEG", quality=90, subsampling=0)
                    encoded = result.getvalue()
                    if len(encoded) > self.settings.max_upload_bytes:
                        raise AppError(413, "evidence_limit", "Re-encoded evidence is too large.")
                    return encoded, clean.width, clean.height, hashlib.sha256(encoded).hexdigest()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise AppError(
                422, "invalid_image", "Image could not be safely decoded. Choose another photo."
            ) from exc

    def finalize(self, draft_id: str, photo_id: str) -> None:
        data = self.read(draft_id, draft=True)
        self.check_quota(len(data))
        final = self.path(photo_id)
        staged = final.with_suffix(".part")
        self.write_private(staged, data)
        os.replace(staged, final)
        self.sync_dir(self.photos)

    def check_quota(self, incoming: int) -> None:
        used = sum(
            p.stat().st_size
            for folder in (self.drafts, self.photos)
            for p in folder.iterdir()
            if ASSET.fullmatch(p.name) and p.is_file() and not p.is_symlink()
        )
        if used + incoming > self.settings.max_evidence_bytes:
            raise AppError(
                409,
                "evidence_quota",
                "Local evidence quota reached. Discard drafts or review/delete records before uploading.",
            )

    def cleanup(self, referenced: set[str]) -> None:
        for folder in (self.drafts, self.photos):
            for path in folder.iterdir():
                if not ASSET.fullmatch(path.name):
                    continue
                if folder == self.drafts or path.suffix == ".part" or path.stem not in referenced:
                    path.unlink(missing_ok=True)
            self.sync_dir(folder)
