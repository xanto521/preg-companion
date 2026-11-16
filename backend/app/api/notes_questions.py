from datetime import UTC, date, datetime, time
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy import select

from app.api.auth import require_recorder
from app.api.checkups import find_checkup
from app.db.connection import start_write
from app.db.models import Note, Question, utc_now
from app.db.session import Database

router = APIRouter(tags=["notes and questions"], dependencies=[Depends(require_recorder)])
Tag = Annotated[str, Field(min_length=1, max_length=30)]
QuestionStatus = Literal["open", "asked", "answered"]


class NoteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    occurred_on: date
    title: str | None = Field(default=None, max_length=100)
    body: str = Field(min_length=1, max_length=6000)
    tags: list[Tag] = Field(default_factory=list, max_length=15)
    viewer_visible: bool = False


class NoteEdit(NoteInput):
    version: PositiveInt


class NoteRecord(BaseModel):
    id: int
    version: int
    occurred_on: date
    title: str | None
    body: str | None
    tags: list[str]
    viewer_visible: bool


class QuestionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=1, max_length=1000)
    status: QuestionStatus = "open"
    checkup_id: PositiveInt | None = None
    answer: str | None = Field(default=None, max_length=4000)


class QuestionEdit(QuestionInput):
    version: PositiveInt


class QuestionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    text: str
    status: QuestionStatus
    checkup_id: int | None
    answer: str | None


def require_record(db: Database, model: type[Note] | type[Question], record_id: int, version: int):
    record = db.get(model, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(404, "这条记录不存在。")
    if record.version != version:
        raise HTTPException(409, "记录已更新，请重新打开后再修改。")
    return record


def note_zone(request: Request) -> ZoneInfo:
    return ZoneInfo(request.app.state.settings.timezone)


def describe_note(note: Note, zone: ZoneInfo) -> NoteRecord:
    return NoteRecord(
        id=note.id, version=note.version,
        occurred_on=note.occurred_at.replace(tzinfo=UTC).astimezone(zone).date(),
        title=note.title, body=note.body, tags=note.tags or [], viewer_visible=note.viewer_visible,
    )


def write_note(note: Note, payload: NoteInput, zone: ZoneInfo, db: Database) -> NoteRecord:
    if note.occurred_at is None or note.occurred_at.replace(tzinfo=UTC).astimezone(zone).date() != payload.occurred_on:
        try:
            note.occurred_at = datetime.combine(payload.occurred_on, time.min, zone).astimezone(UTC).replace(tzinfo=None)
        except OverflowError as exc:
            raise HTTPException(422, "备注日期超出可记录的范围。") from exc
    note.title = payload.title or None
    note.body = payload.body
    note.tags = list(dict.fromkeys(payload.tags))
    note.viewer_visible = payload.viewer_visible
    db.add(note)
    db.commit()
    return describe_note(note, zone)


@router.get("/notes")
def list_notes(request: Request, db: Database) -> list[NoteRecord]:
    zone = note_zone(request)
    items = db.scalars(select(Note).where(Note.deleted_at.is_(None)).order_by(Note.occurred_at.desc(), Note.id.desc()))
    return [describe_note(item, zone) for item in items]


@router.post("/notes", status_code=201)
def create_note(payload: NoteInput, request: Request, db: Database) -> NoteRecord:
    return write_note(Note(), payload, note_zone(request), db)


@router.put("/notes/{note_id}")
def edit_note(note_id: int, payload: NoteEdit, request: Request, db: Database) -> NoteRecord:
    start_write(db)
    note = require_record(db, Note, note_id, payload.version)
    note.version += 1
    return write_note(note, payload, note_zone(request), db)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, version: PositiveInt, db: Database) -> None:
    start_write(db)
    note = require_record(db, Note, note_id, version)
    note.deleted_at = utc_now()
    note.version += 1
    db.commit()


def write_question(question: Question, payload: QuestionInput, db: Database) -> QuestionRecord:
    if payload.checkup_id is not None and payload.checkup_id != question.checkup_id:
        find_checkup(db, payload.checkup_id)
    question.text = payload.text
    question.status = payload.status
    question.checkup_id = payload.checkup_id
    question.answer = payload.answer or None
    if payload.status == "answered":
        question.answered_at = question.answered_at or utc_now()
    else:
        question.answered_at = None
    db.add(question)
    db.commit()
    return QuestionRecord.model_validate(question)


@router.get("/questions")
def list_questions(db: Database) -> list[QuestionRecord]:
    items = db.scalars(select(Question).where(Question.deleted_at.is_(None)).order_by(Question.created_at.desc(), Question.id.desc()))
    return [QuestionRecord.model_validate(item) for item in items]


@router.post("/questions", status_code=201)
def create_question(payload: QuestionInput, db: Database) -> QuestionRecord:
    start_write(db)
    return write_question(Question(), payload, db)


@router.put("/questions/{question_id}")
def edit_question(question_id: int, payload: QuestionEdit, db: Database) -> QuestionRecord:
    start_write(db)
    question = require_record(db, Question, question_id, payload.version)
    question.version += 1
    return write_question(question, payload, db)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, version: PositiveInt, db: Database) -> None:
    start_write(db)
    question = require_record(db, Question, question_id, version)
    question.deleted_at = utc_now()
    question.version += 1
    db.commit()
