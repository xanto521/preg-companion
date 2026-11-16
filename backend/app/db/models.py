from datetime import UTC, date, datetime, time

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy import false, text, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    # Store UTC without an offset so SQLite and PostgreSQL use the same representation.
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class VersionedRecord:
    version: Mapped[int] = mapped_column(server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class SoftDeletedRecord(VersionedRecord):
    deleted_at: Mapped[datetime | None]


class Pregnancy(VersionedRecord, Base):
    __tablename__ = "pregnancy"

    id: Mapped[int] = mapped_column(primary_key=True)
    edd_date: Mapped[date]
    edd_source: Mapped[str] = mapped_column(Text)
    lmp_date: Mapped[date | None]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class EddHistory(Base):
    __tablename__ = "edd_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregnancy_id: Mapped[int] = mapped_column(ForeignKey("pregnancy.id"))
    edd_date: Mapped[date]
    source: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(default=utc_now)


class Checkup(SoftDeletedRecord, Base):
    __tablename__ = "checkup"
    __table_args__ = (Index("ix_checkup_visit_date", "visit_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pregnancy_id: Mapped[int] = mapped_column(ForeignKey("pregnancy.id"))
    visit_date: Mapped[date]
    visit_time: Mapped[time | None]
    hospital: Mapped[str | None] = mapped_column(Text)
    doctor: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    advice: Mapped[str | None] = mapped_column(Text)
    next_visit_date: Mapped[date | None]
    next_visit_time: Mapped[time | None]
    viewer_visible: Mapped[bool] = mapped_column(server_default=true())
    viewer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class MetricDefinition(Base):
    __tablename__ = "metric_def"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(Text)
    ref_low: Mapped[float | None]
    ref_high: Mapped[float | None]


class MetricValue(Base):
    __tablename__ = "metric_value"
    __table_args__ = (Index("ix_metric_value_code_measured_at", "code", "measured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("metric_def.code"))
    checkup_id: Mapped[int | None] = mapped_column(ForeignKey("checkup.id"))
    daily_log_id: Mapped[int | None] = mapped_column(ForeignKey("daily_log.id"))
    measured_at: Mapped[datetime]
    ga_days: Mapped[int | None]
    value_num: Mapped[float | None]
    value_text: Mapped[str | None] = mapped_column(Text)


class DailyLog(SoftDeletedRecord, Base):
    __tablename__ = "daily_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    log_date: Mapped[date] = mapped_column(unique=True)
    mood: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    viewer_visible: Mapped[bool] = mapped_column(server_default=true())


class MealEntry(Base):
    __tablename__ = "meal_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(ForeignKey("daily_log.id"))
    meal_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    attachment_id: Mapped[int | None] = mapped_column(ForeignKey("attachment.id"))


class SymptomEntry(Base):
    __tablename__ = "symptom_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(ForeignKey("daily_log.id"))
    tag: Mapped[str] = mapped_column(Text)
    severity: Mapped[int | None]
    note: Mapped[str | None] = mapped_column(Text)


class SupplementPlan(SoftDeletedRecord, Base):
    __tablename__ = "supplement_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    dosage: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date]
    end_date: Mapped[date | None]
    remind_time: Mapped[time | None]
    rrule: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(server_default=true())
    viewer_visible: Mapped[bool] = mapped_column(server_default=false())


class SupplementCheck(Base):
    __tablename__ = "supplement_check"
    __table_args__ = (UniqueConstraint("plan_id", "check_date", name="uq_supplement_check_plan_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("supplement_plan.id"))
    check_date: Mapped[date]
    taken: Mapped[bool]


class Question(SoftDeletedRecord, Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    checkup_id: Mapped[int | None] = mapped_column(ForeignKey("checkup.id"))
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    answered_at: Mapped[datetime | None]


class Note(SoftDeletedRecord, Base):
    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime]
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True))
    viewer_visible: Mapped[bool] = mapped_column(server_default=false())
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = (Index("ix_attachment_owner", "owner_type", "owner_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_type: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int]
    kind: Mapped[str] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None]
    sha256: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class MilestoneRule(SoftDeletedRecord, Base):
    __tablename__ = "milestone_rule"
    __table_args__ = (CheckConstraint("start_ga_days <= end_ga_days", name="ck_milestone_window"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    start_ga_days: Mapped[int]
    end_ga_days: Mapped[int]
    enabled: Mapped[bool] = mapped_column(server_default=true())
    note: Mapped[str | None] = mapped_column(Text)


class ShareToken(Base):
    __tablename__ = "share_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    scope: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
