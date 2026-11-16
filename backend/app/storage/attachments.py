from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

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


def stage_attachment(source: BinaryIO, temp_path: Path) -> tuple[str, str, int, str]:
    digest = sha256()
    size = 0
    first = source.read(UPLOAD_CHUNK)
    mime, extension = identify_file(first)
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
