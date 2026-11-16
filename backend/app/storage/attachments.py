from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Attachment, utc_now

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_CHUNK = 256 * 1024


class InvalidAttachment(ValueError):
    pass


def identify_file(header: bytes) -> tuple[str, str]:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if header.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    raise InvalidAttachment("请选择 JPG、PNG、WebP 图片或 PDF 文件。")


def stage_attachment(source: BinaryIO, temp_path: Path, *, image_only: bool = False) -> tuple[str, str, int, str]:
    digest = sha256()
    size = 0
    first = source.read(UPLOAD_CHUNK)
    mime, extension = identify_file(first)
    if image_only and not mime.startswith("image/"):
        raise InvalidAttachment("请选择 JPG、PNG 或 WebP 图片。")
    with temp_path.open("wb") as target:
        chunk = first
        while chunk:
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise InvalidAttachment("每个附件最多 20 MB。")
            digest.update(chunk)
            target.write(chunk)
            chunk = source.read(UPLOAD_CHUNK)
    return mime, extension, size, digest.hexdigest()


def safe_filename(filename: str | None, extension: str) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(char for char in name if char.isprintable()).strip()[:180] or f"附件{extension}"


def publish_blob(
    db: Session, root: Path, temp_path: Path, digest: str, extension: str, existing: Attachment | None = None,
) -> str:
    stored = existing or db.scalar(
        select(Attachment).where(Attachment.sha256 == digest).order_by(Attachment.id).limit(1)
    )
    relative = stored.storage_path if stored else f"{utc_now():%Y/%m}/{digest}{extension}"
    destination = root / relative
    if not destination.is_file():
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp_path.replace(destination)
    return relative
