from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator
from sqlalchemy import delete, select
from starlette.datastructures import UploadFile

from app.api.attachment_requests import attachment_response, attachment_root, check_upload
from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import Attachment, DailyLog, MealEntry, SymptomEntry
from app.db.session import Database
from app.storage.attachments import InvalidAttachment, publish_blob, safe_filename, stage_attachment

router = APIRouter(prefix="/daily", tags=["daily"], dependencies=[Depends(require_recorder)])
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
ShortText = Annotated[str, Field(min_length=1, max_length=40)]


class DailyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    version: NonNegativeInt
    mood: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=4000)
    viewer_visible: bool = True
    meals: dict[MealType, Annotated[str, Field(max_length=500)]] = Field(default_factory=dict)
    symptoms: list[ShortText] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_symptoms(self) -> "DailyInput":
        if len(set(self.symptoms)) != len(self.symptoms):
            raise ValueError("症状标签不能重复。")
        return self


class Photo(BaseModel):
    id: int
    filename: str | None


class DailyRecord(DailyInput):
    log_date: date
    photos: dict[str, Photo]


def find_day(db: Database, day: date) -> DailyLog | None:
    return db.scalar(select(DailyLog).where(DailyLog.log_date == day, DailyLog.deleted_at.is_(None)))


def meals_for(db: Database, log_id: int) -> dict[str, MealEntry]:
    meals = db.scalars(select(MealEntry).where(MealEntry.daily_log_id == log_id).order_by(MealEntry.id))
    return {meal.meal_type: meal for meal in meals}


def describe(db: Database, day: date, log: DailyLog | None) -> DailyRecord:
    if log is None:
        return DailyRecord(log_date=day, version=0, photos={})

    meals = meals_for(db, log.id)
    photos = {}
    for kind, meal in meals.items():
        if meal.attachment_id is not None:
            attachment = db.get(Attachment, meal.attachment_id)
            if attachment is not None:
                photos[kind] = Photo(id=attachment.id, filename=attachment.filename)
    symptoms = db.scalars(select(SymptomEntry.tag).where(SymptomEntry.daily_log_id == log.id).order_by(SymptomEntry.id))
    return DailyRecord(
        log_date=day, version=log.version, mood=log.mood, note=log.note,
        viewer_visible=log.viewer_visible,
        meals={kind: meal.description for kind, meal in meals.items() if meal.description},
        photos=photos, symptoms=list(dict.fromkeys(symptoms)),
    )


def enforce_version(log: DailyLog | None, version: int) -> None:
    if (log.version if log else 0) != version:
        raise HTTPException(409, "当天记录已更新，请重新打开后再修改。")


@router.get("/{day}")
def get_day(day: date, db: Database) -> DailyRecord:
    return describe(db, day, find_day(db, day))


@router.put("/{day}")
def save_day(day: date, payload: DailyInput, db: Database) -> DailyRecord:
    start_write(db)
    log = db.scalar(select(DailyLog).where(DailyLog.log_date == day))
    visible_log = log if log and log.deleted_at is None else None
    enforce_version(visible_log, payload.version)
    if log is None:
        log = DailyLog(log_date=day)
        db.add(log)
    else:
        log.version += 1
    log.deleted_at = None
    log.mood = payload.mood or None
    log.note = payload.note or None
    log.viewer_visible = payload.viewer_visible
    db.flush()

    entries = meals_for(db, log.id)
    for kind, description in payload.meals.items():
        if description and kind not in entries:
            entries[kind] = MealEntry(daily_log_id=log.id, meal_type=kind)
            db.add(entries[kind])
    for kind, meal in entries.items():
        meal.description = payload.meals.get(kind) or None
        if not meal.description and meal.attachment_id is None:
            db.delete(meal)
    existing = list(db.scalars(select(SymptomEntry).where(SymptomEntry.daily_log_id == log.id)))
    retained = set()
    for symptom in existing:
        if symptom.tag in payload.symptoms and symptom.tag not in retained:
            retained.add(symptom.tag)
        else:
            db.delete(symptom)
    db.add_all(SymptomEntry(daily_log_id=log.id, tag=tag) for tag in payload.symptoms if tag not in retained)
    result = describe(db, day, log)
    db.commit()
    return result


def store_photo(day: date, kind: MealType, version: int, upload: UploadFile, root: Path, db: Database) -> DailyRecord:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root) as staging:
        temp_path = Path(staging) / "photo"
        try:
            mime, extension, size, digest = stage_attachment(upload.file, temp_path, image_only=True)
        except InvalidAttachment as exc:
            raise HTTPException(422, str(exc)) from exc

        start_write(db)
        log = find_day(db, day)
        if log is None:
            raise HTTPException(404, "请先保存当天记录。")
        enforce_version(log, version)
        meal = meals_for(db, log.id).get(kind)
        if meal is None:
            meal = MealEntry(daily_log_id=log.id, meal_type=kind)
            db.add(meal)

        photo = db.get(Attachment, meal.attachment_id) if meal.attachment_id is not None else None
        if photo and photo.sha256 == digest:
            publish_blob(db, root, temp_path, digest, extension, photo)
        else:
            path = publish_blob(db, root, temp_path, digest, extension)
            photo = Attachment(
                owner_type="daily", owner_id=log.id, kind="photo",
                filename=safe_filename(upload.filename, extension), mime=mime,
                size_bytes=size, sha256=digest, storage_path=path,
            )
            db.add(photo)
            db.flush()
            meal.attachment_id = photo.id
            log.version += 1

        result = describe(db, day, log)
        db.commit()
        return result


@router.post("/{day}/meals/{kind}/photo")
async def upload_photo(day: date, kind: MealType, version: NonNegativeInt, request: Request, db: Database) -> DailyRecord:
    check_upload(request)
    async with request.form(max_files=1, max_fields=0, max_part_size=1024) as form:
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(422, "请选择饮食照片。")
        return await run_in_threadpool(store_photo, day, kind, version, upload, attachment_root(request), db)


@router.get("/{day}/meals/{kind}/photo/{photo_id}")
def get_photo(day: date, kind: MealType, photo_id: int, request: Request, db: Database) -> FileResponse:
    log = find_day(db, day)
    meal = meals_for(db, log.id).get(kind) if log else None
    photo = db.get(Attachment, photo_id) if meal and meal.attachment_id == photo_id else None
    if photo is None or photo.owner_type != "daily" or photo.owner_id != log.id:
        raise HTTPException(404, "照片不存在。")
    return attachment_response(request, photo, inline=True)


@router.delete("/{day}/meals/{kind}/photo")
def remove_photo(day: date, kind: MealType, version: NonNegativeInt, db: Database) -> DailyRecord:
    start_write(db)
    log = find_day(db, day)
    if log is None:
        raise HTTPException(404, "当天记录不存在。")
    enforce_version(log, version)
    meal = meals_for(db, log.id).get(kind)
    if meal and meal.attachment_id is not None:
        meal.attachment_id = None
        if not meal.description:
            db.delete(meal)
        log.version += 1
    result = describe(db, day, log)
    db.commit()
    return result
