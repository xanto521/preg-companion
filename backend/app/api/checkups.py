from datetime import UTC, date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveInt, model_validator
from sqlalchemy import delete, select
from starlette.datastructures import UploadFile

from app.api.attachment_requests import attachment_response, attachment_root, check_upload
from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import Attachment, Checkup, MetricDefinition, MetricValue, Pregnancy, utc_now
from app.db.session import Database
from app.domain.gestation import gestational_days
from app.domain.pregnancy import current_pregnancy
from app.storage.attachments import InvalidAttachment, publish_blob, safe_filename, stage_attachment

router = APIRouter(tags=["checkups"], dependencies=[Depends(require_recorder)])
AttachmentKind = Literal["report", "ultrasound", "other"]
ATTACHMENT_KINDS = {"report", "ultrasound", "other"}


class CheckupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    visit_date: date
    visit_time: time | None = None
    hospital: str | None = Field(default=None, max_length=150)
    doctor: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=6000)
    advice: str | None = Field(default=None, max_length=6000)
    viewer_visible: bool = True
    viewer_note: str | None = Field(default=None, max_length=2000)
    metrics: dict[str, FiniteFloat] = Field(default_factory=dict, max_length=40)

    @model_validator(mode="after")
    def validate_time(self) -> "CheckupInput":
        if self.visit_time is not None and self.visit_time.tzinfo is not None:
            raise ValueError("请填写当地时间。")
        return self


class CheckupEdit(CheckupInput):
    version: PositiveInt


class CheckupSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    updated_at: datetime
    visit_date: date
    visit_time: time | None
    hospital: str | None
    doctor: str | None
    ga_days: int | None


class AttachmentDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str | None
    mime: str | None
    size_bytes: int | None


class CheckupDetails(CheckupSummary):
    summary: str | None
    advice: str | None
    viewer_visible: bool
    viewer_note: str | None
    metrics: dict[str, float]
    attachments: list[AttachmentDetails]


class MetricOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    unit: str | None


def find_checkup(db: Database, checkup_id: int) -> Checkup:
    checkup = db.get(Checkup, checkup_id)
    if not checkup or checkup.deleted_at is not None:
        raise HTTPException(404, "这条产检记录不存在。")
    return checkup


def attachments_for(checkup_id: int):
    return select(Attachment).where(
        Attachment.owner_type == "checkup", Attachment.owner_id == checkup_id,
    )


def checkup_details(db: Database, checkup: Checkup) -> CheckupDetails:
    metrics = db.scalars(
        select(MetricValue)
        .where(MetricValue.checkup_id == checkup.id, MetricValue.value_num.is_not(None))
        .order_by(MetricValue.measured_at, MetricValue.id)
    )
    attachments = db.scalars(attachments_for(checkup.id).order_by(Attachment.id))
    return CheckupDetails(
        **CheckupSummary.model_validate(checkup).model_dump(),
        summary=checkup.summary, advice=checkup.advice, viewer_visible=checkup.viewer_visible,
        viewer_note=checkup.viewer_note,
        metrics={entry.code: entry.value_num for entry in metrics if entry.value_num is not None},
        attachments=[AttachmentDetails.model_validate(attachment) for attachment in attachments],
    )


def assert_version(checkup: Checkup, version: int) -> None:
    if checkup.version != version:
        raise HTTPException(409, "记录已更新，请重新打开后再操作。")


def save_checkup(
    payload: CheckupInput, checkup: Checkup, pregnancy: Pregnancy, request: Request, db: Database,
) -> CheckupDetails:
    metric_codes = set(db.scalars(
        select(MetricDefinition.code)
        .where(MetricDefinition.code.in_(payload.metrics), MetricDefinition.value_type == "num")
    ))
    if metric_codes != set(payload.metrics):
        raise HTTPException(422, "有无法识别的产检指标，请重新打开表单。")

    visit_changed = checkup.visit_date != payload.visit_date
    time_changed = checkup.visit_time != payload.visit_time
    if visit_changed or checkup.ga_days is None:
        checkup.ga_days = gestational_days(pregnancy.edd_date, payload.visit_date)
    for key, value in payload.model_dump(exclude={"metrics", "version"}).items():
        setattr(checkup, key, None if value == "" else value)
    db.add(checkup)
    db.flush()

    zone = ZoneInfo(request.app.state.settings.timezone)
    measured_at = datetime.combine(checkup.visit_date, checkup.visit_time or time.min, zone)
    measured_at = measured_at.astimezone(UTC).replace(tzinfo=None)
    existing_metrics = list(db.scalars(
        select(MetricValue)
        .where(
            MetricValue.checkup_id == checkup.id, MetricValue.value_num.is_not(None),
            MetricValue.code.in_(select(MetricDefinition.code).where(MetricDefinition.value_type == "num")),
        )
        .order_by(MetricValue.id.desc())
    ))
    pending = dict(payload.metrics)
    for entry in existing_metrics:
        if entry.code not in pending:
            db.delete(entry)
            continue
        entry.value_num = pending.pop(entry.code)
        if visit_changed:
            entry.ga_days = checkup.ga_days
        if visit_changed or time_changed:
            entry.measured_at = measured_at
    for code, value in pending.items():
        db.add(MetricValue(
            checkup_id=checkup.id, code=code, measured_at=measured_at,
            ga_days=checkup.ga_days, value_num=value,
        ))
    db.commit()
    return checkup_details(db, checkup)


@router.get("/metrics/definitions")
def metrics_definitions(db: Database) -> list[MetricOption]:
    options = db.scalars(
        select(MetricDefinition).where(MetricDefinition.value_type == "num").order_by(MetricDefinition.code)
    )
    return [MetricOption.model_validate(option) for option in options]


@router.get("/checkups")
def list_checkups(db: Database) -> list[CheckupSummary]:
    records = db.scalars(
        select(Checkup)
        .where(Checkup.deleted_at.is_(None))
        .order_by(Checkup.visit_date.desc(), Checkup.visit_time.desc(), Checkup.id.desc())
    )
    return [CheckupSummary.model_validate(record) for record in records]


@router.post("/checkups", status_code=201)
def create_checkup(payload: CheckupInput, request: Request, db: Database) -> CheckupDetails:
    start_write(db)
    pregnancy = current_pregnancy(db)
    if pregnancy is None:
        raise HTTPException(409, "请先设置预产期。")
    checkup = Checkup(pregnancy_id=pregnancy.id)
    return save_checkup(payload, checkup, pregnancy, request, db)


@router.get("/checkups/{checkup_id}")
def get_checkup(checkup_id: int, db: Database) -> CheckupDetails:
    return checkup_details(db, find_checkup(db, checkup_id))


@router.put("/checkups/{checkup_id}")
def edit_checkup(checkup_id: int, payload: CheckupEdit, request: Request, db: Database) -> CheckupDetails:
    start_write(db)
    checkup = find_checkup(db, checkup_id)
    assert_version(checkup, payload.version)
    pregnancy = db.get(Pregnancy, checkup.pregnancy_id)
    if pregnancy is None:
        raise HTTPException(409, "找不到这条记录所属的孕期。")
    checkup.version += 1
    return save_checkup(payload, checkup, pregnancy, request, db)


@router.delete("/checkups/{checkup_id}", status_code=204)
def delete_checkup(checkup_id: int, version: PositiveInt, db: Database) -> None:
    start_write(db)
    checkup = find_checkup(db, checkup_id)
    assert_version(checkup, version)
    checkup.deleted_at = utc_now()
    checkup.version += 1
    db.commit()


def store_attachment(
    checkup_id: int, kind: AttachmentKind, upload: UploadFile, root: Path, db: Database,
) -> AttachmentDetails:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root) as staging:
        temp_path = Path(staging) / "upload"
        try:
            mime, extension, size, digest = stage_attachment(upload.file, temp_path)
        except InvalidAttachment as exc:
            raise HTTPException(422, str(exc)) from exc

        start_write(db)
        checkup = find_checkup(db, checkup_id)
        same = db.scalar(attachments_for(checkup.id).where(
            Attachment.sha256 == digest, Attachment.kind == kind,
        ).limit(1))
        if same is not None and (root / same.storage_path).is_file():
            return AttachmentDetails.model_validate(same)

        storage_path = publish_blob(db, root, temp_path, digest, extension, same)
        if same is None:
            filename = safe_filename(upload.filename, extension)
            same = Attachment(
                owner_type="checkup", owner_id=checkup.id, kind=kind, filename=filename,
                mime=mime, size_bytes=size, sha256=digest, storage_path=storage_path,
            )
            db.add(same)
        db.commit()
        return AttachmentDetails.model_validate(same)


@router.post("/checkups/{checkup_id}/attachments", status_code=201)
async def upload_attachment(checkup_id: int, request: Request, db: Database) -> AttachmentDetails:
    check_upload(request)
    async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
        upload = form.get("file")
        kind = form.get("kind", "report")
        if not isinstance(upload, UploadFile) or not isinstance(kind, str) or kind not in ATTACHMENT_KINDS:
            raise HTTPException(422, "请选择附件和正确的附件类型。")
        return await run_in_threadpool(store_attachment, checkup_id, kind, upload, attachment_root(request), db)


@router.get("/checkups/{checkup_id}/attachments/{attachment_id}")
def download_attachment(checkup_id: int, attachment_id: int, request: Request, db: Database) -> FileResponse:
    find_checkup(db, checkup_id)
    attachment = db.scalar(attachments_for(checkup_id).where(Attachment.id == attachment_id))
    if attachment is None:
        raise HTTPException(404, "附件不存在。")

    return attachment_response(request, attachment)
