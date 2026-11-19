from datetime import date, datetime, time as LocalTime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator
from sqlalchemy import select

from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import Appointment, utc_now
from app.db.session import Database

router = APIRouter(prefix="/appointments", tags=["appointments"], dependencies=[Depends(require_recorder)])


class AppointmentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    day: date
    time: LocalTime | None = None
    hospital: str | None = Field(default=None, max_length=150)
    title: str | None = Field(default=None, max_length=150)
    viewer_visible: bool = False

    @field_validator("time")
    @classmethod
    def local_time(cls, value: LocalTime | None) -> LocalTime | None:
        if value is not None and value.tzinfo is not None:
            raise ValueError("请填写当地时间。")
        return value


class AppointmentEdit(AppointmentInput):
    version: PositiveInt


class AppointmentDetails(AppointmentEdit):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime


def appointment_for_write(db: Database, appointment_id: int, version: int) -> Appointment:
    start_write(db)
    record = db.get(Appointment, appointment_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(404, "这条预约不存在。")
    if record.version != version:
        raise HTTPException(409, "预约已更新，请重新打开后再操作。")
    record.version += 1
    return record


@router.get("")
def list_appointments(db: Database) -> list[AppointmentDetails]:
    records = db.scalars(select(Appointment).where(Appointment.deleted_at.is_(None)).order_by(
        Appointment.day, Appointment.time, Appointment.id,
    ))
    return [AppointmentDetails.model_validate(record) for record in records]


@router.post("", status_code=201)
def create_appointment(payload: AppointmentInput, db: Database) -> AppointmentDetails:
    start_write(db)
    record = Appointment(**payload.model_dump())
    db.add(record)
    db.commit()
    return AppointmentDetails.model_validate(record)


@router.put("/{appointment_id}")
def edit_appointment(appointment_id: int, payload: AppointmentEdit, db: Database) -> AppointmentDetails:
    record = appointment_for_write(db, appointment_id, payload.version)
    for key, value in payload.model_dump(exclude={"version"}).items():
        setattr(record, key, value)
    db.commit()
    return AppointmentDetails.model_validate(record)


@router.delete("/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: int, version: PositiveInt, db: Database) -> None:
    record = appointment_for_write(db, appointment_id, version)
    record.deleted_at = utc_now()
    db.commit()
