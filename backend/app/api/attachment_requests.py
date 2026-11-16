from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from app.db.models import Attachment
from app.storage.attachments import MAX_UPLOAD_BYTES


def check_upload(request: Request) -> None:
    try:
        length = int(request.headers["content-length"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(411, "上传需包含文件大小。") from exc
    if length < 0 or length > MAX_UPLOAD_BYTES + 64 * 1024:
        raise HTTPException(413, "每个附件最多 20 MB。")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "请通过附件表单上传文件。")


def attachment_root(request: Request) -> Path:
    return request.app.state.settings.database_path.parent / "attachments"


def attachment_response(request: Request, attachment: Attachment, *, inline: bool = False) -> FileResponse:
    root = attachment_root(request).resolve()
    path = (root / attachment.storage_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "附件文件不存在。")
    return FileResponse(
        path,
        filename=attachment.filename or "附件",
        media_type=attachment.mime or "application/octet-stream",
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )
