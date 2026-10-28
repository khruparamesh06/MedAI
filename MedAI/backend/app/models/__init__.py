"""SQLAlchemy ORM models. Importing this package registers every table on Base.metadata."""
from datetime import date, datetime, time

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer,
    String, Text, Time, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import (
    AccountStatus, AnalysisStatus, AppointmentStatus, AssignmentStatus, DoctorProfileStatus,
    ReviewAgreement, ReviewStatus, UploadStatus, UserRole,
)


def _enum(e, name: str):
    # VARCHAR + CHECK constraint: portable between SQLite and PostgreSQL, simple to migrate.
    return Enum(e, name=name, native_enum=False, create_constraint=True, length=32,
                values_callable=lambda x: [m.value for m in x])


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), index=True, nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        _enum(AccountStatus, "account_status"), default=AccountStatus.active, nullable=False)
    # Incremented to invalidate all previously issued tokens (logout everywhere, disable, password change).
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Set for accounts created with an administrator-chosen temporary password.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False)

    # Patient demographic fields (nullable; only used for patients)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(32))

    doctor_profile: Mapped["DoctorProfile | None"] = relationship(
        back_populates="user", uselist=False, foreign_keys="DoctorProfile.user_id")


class DoctorProfile(TimestampMixin, Base):
    __tablename__ = "doctor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    license_number: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    clinic_location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    status: Mapped[DoctorProfileStatus] = mapped_column(
        _enum(DoctorProfileStatus, "doctor_profile_status"), default=DoctorProfileStatus.draft,
        index=True, nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("years_experience >= 0 AND years_experience <= 80", name="years_range"),)

    user: Mapped[User] = relationship(back_populates="doctor_profile", foreign_keys=[user_id])
    availability: Mapped[list["DoctorAvailability"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan",
        order_by="(DoctorAvailability.weekday, DoctorAvailability.start_time)")


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="weekday_range"),
        CheckConstraint("start_time < end_time", name="time_order"),
    )

    profile: Mapped[DoctorProfile] = relationship(back_populates="availability")


ACTIVE_ASSIGNMENT = "status IN ('pending', 'approved')"


class Assignment(TimestampMixin, Base):
    """A patient's request to be under a doctor's care. Only 'approved' grants the doctor access."""
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        _enum(AssignmentStatus, "assignment_status"), default=AssignmentStatus.pending, index=True, nullable=False)
    request_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    decision_note: Mapped[str | None] = mapped_column(Text)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # At most one pending/approved assignment per patient-doctor pair (DB-level guarantee).
        Index("uq_assignment_active_pair", "patient_id", "doctor_id", unique=True,
              sqlite_where=text(ACTIVE_ASSIGNMENT), postgresql_where=text(ACTIVE_ASSIGNMENT)),
        CheckConstraint("patient_id <> doctor_id", name="distinct_users"),
    )

    patient: Mapped[User] = relationship(foreign_keys=[patient_id])
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])


BLOCKING_APPOINTMENT = "status IN ('requested', 'confirmed')"


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        _enum(AppointmentStatus, "appointment_status"), default=AppointmentStatus.requested,
        index=True, nullable=False)
    doctor_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # A doctor cannot have two open appointments starting at the same time.
        Index("uq_appointment_doctor_slot", "doctor_id", "scheduled_at", unique=True,
              sqlite_where=text(BLOCKING_APPOINTMENT), postgresql_where=text(BLOCKING_APPOINTMENT)),
        CheckConstraint("duration_minutes > 0 AND duration_minutes <= 240", name="duration_range"),
    )

    patient: Mapped[User] = relationship(foreign_keys=[patient_id])
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])


class XrayUpload(TimestampMixin, Base):
    __tablename__ = "xray_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # display only, never a path
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # uuid4 hex + ext
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    view_position: Mapped[str | None] = mapped_column(String(16))  # PA / AP / lateral, as stated by the patient
    patient_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[UploadStatus] = mapped_column(
        _enum(UploadStatus, "upload_status"), default=UploadStatus.uploaded, index=True, nullable=False)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    analyses: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan", order_by="AnalysisResult.id.desc()")
    reviews: Mapped[list["ClinicalReview"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan", order_by="ClinicalReview.id.desc()")


class AnalysisResult(Base):
    """Structured output of one genuine model inference run (or a recorded failure)."""
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("xray_uploads.id", ondelete="CASCADE"), index=True, nullable=False)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[AnalysisStatus] = mapped_column(_enum(AnalysisStatus, "analysis_status"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    weights_sha256: Mapped[str | None] = mapped_column(String(64))
    score_type: Mapped[str] = mapped_column(String(64), nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # [{"label": str, "score": float}]
    preprocessing: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    upload: Mapped[XrayUpload] = relationship(back_populates="analyses")


class ClinicalReview(TimestampMixin, Base):
    """A doctor's independent read of an X-ray (and optionally of the AI output)."""
    __tablename__ = "clinical_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("xray_uploads.id", ondelete="CASCADE"), index=True, nullable=False)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_results.id", ondelete="SET NULL"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    impression: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ai_agreement: Mapped[ReviewAgreement] = mapped_column(
        _enum(ReviewAgreement, "review_agreement"), nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus, "review_status"), default=ReviewStatus.draft, nullable=False)

    upload: Mapped[XrayUpload] = relationship(back_populates="reviews")
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])


class ClinicalNote(TimestampMixin, Base):
    """Free-text clinician notes about an assigned patient."""
    __tablename__ = "clinical_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visible_to_patient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    doctor: Mapped[User] = relationship(foreign_keys=[doctor_id])


class RevokedToken(Base):
    """Individually revoked access tokens (sign-out). Rows can be purged once `expires_at` has passed."""
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])


__all__ = [
    "User", "DoctorProfile", "DoctorAvailability", "Assignment", "Appointment", "XrayUpload",
    "AnalysisResult", "ClinicalReview", "ClinicalNote", "AuditEvent", "RevokedToken",
    "UserRole", "AccountStatus", "DoctorProfileStatus", "AssignmentStatus", "AppointmentStatus",
    "UploadStatus", "AnalysisStatus", "ReviewAgreement", "ReviewStatus",
]
