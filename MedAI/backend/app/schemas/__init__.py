"""Pydantic request/response schemas. Field names here are the API contract used by the frontend."""
from datetime import date, datetime, time
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import (
    AccountStatus, AnalysisStatus, AppointmentStatus, AssignmentStatus, DoctorProfileStatus,
    ReviewAgreement, ReviewStatus, UploadStatus, UserRole,
)

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    detail: str


# ---------- auth ----------
def _validate_password(value: str) -> str:
    if len(value) < 10:
        raise ValueError("Password must be at least 10 characters long")
    if value.isdigit() or value.isalpha():
        raise ValueError("Password must contain both letters and numbers or symbols")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    date_of_birth: date | None = None
    sex: Literal["female", "male", "other", "prefer_not_to_say"] | None = None
    phone: str | None = Field(default=None, max_length=32)

    _pw = field_validator("password")(_validate_password)

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name is required")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _dob_past(cls, v: date | None) -> date | None:
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("Date of birth must be a past date")
        return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)

    _pw = field_validator("new_password")(_validate_password)


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    status: AccountStatus
    date_of_birth: date | None = None
    sex: str | None = None
    phone: str | None = None
    must_change_password: bool = False
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    date_of_birth: date | None = None
    sex: Literal["female", "male", "other", "prefer_not_to_say"] | None = None
    phone: str | None = Field(default=None, max_length=32)


# ---------- doctors ----------
class AvailabilitySlot(ORM):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _order(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class DoctorProfileUpdate(BaseModel):
    specialty: str = Field(min_length=2, max_length=120)
    license_number: str = Field(min_length=3, max_length=64)
    years_experience: int = Field(ge=0, le=80)
    bio: str = Field(default="", max_length=2000)
    clinic_location: str = Field(default="", max_length=200)


class AvailabilityUpdate(BaseModel):
    slots: list[AvailabilitySlot] = Field(max_length=50)

    @model_validator(mode="after")
    def _no_overlap(self):
        by_day: dict[int, list[AvailabilitySlot]] = {}
        for s in self.slots:
            by_day.setdefault(s.weekday, []).append(s)
        for slots in by_day.values():
            slots.sort(key=lambda s: s.start_time)
            for a, b in zip(slots, slots[1:]):
                if b.start_time < a.end_time:
                    raise ValueError("Availability slots on the same day must not overlap")
        return self


class DoctorProfileOut(ORM):
    id: int
    user_id: int
    specialty: str
    license_number: str
    years_experience: int
    bio: str
    clinic_location: str
    status: DoctorProfileStatus
    review_note: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    availability: list[AvailabilitySlot] = []


class DoctorPublic(BaseModel):
    """What patients see in the directory (no license number or internal review data)."""
    user_id: int
    full_name: str
    specialty: str
    years_experience: int
    bio: str
    clinic_location: str
    availability: list[AvailabilitySlot]


class DoctorAdminOut(BaseModel):
    user: UserOut
    profile: DoctorProfileOut


class DoctorCreateRequest(BaseModel):
    """Administrator-only: create a doctor account (public registration never creates doctors)."""
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    temporary_password: str = Field(min_length=10, max_length=128)

    _pw = field_validator("temporary_password")(_validate_password)


class ReviewDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


# ---------- assignments ----------
class AssignmentCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    reason: str = Field(default="", max_length=1000)


class UserBrief(ORM):
    id: int
    full_name: str
    email: EmailStr


class AssignmentOut(ORM):
    id: int
    patient: UserBrief
    doctor: UserBrief
    status: AssignmentStatus
    request_reason: str
    decision_note: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


# ---------- appointments ----------
class AppointmentCreate(BaseModel):
    """`date` and `start_time` are local times in the clinic time zone (GET /api/health)."""
    doctor_id: int = Field(gt=0)
    date: date
    start_time: time
    reason: str = Field(min_length=3, max_length=1000)
    duration_minutes: int = Field(default=30, ge=15, le=120)


class AppointmentStatusUpdate(BaseModel):
    status: Literal["confirmed", "declined", "cancelled", "completed"]
    note: str | None = Field(default=None, max_length=1000)


class AppointmentOut(ORM):
    id: int
    patient: UserBrief
    doctor: UserBrief
    scheduled_at: datetime
    duration_minutes: int
    reason: str
    status: AppointmentStatus
    doctor_note: str | None = None
    created_at: datetime


# ---------- x-rays / AI ----------
class Finding(BaseModel):
    label: str
    display_name: str
    score: float
    above_operating_threshold: bool | None = None


class AnalysisOut(ORM):
    id: int
    upload_id: int
    status: AnalysisStatus
    model_name: str
    model_version: str
    weights_sha256: str | None = None
    score_type: str
    score_description: str | None = None
    findings: list[Finding]
    preprocessing: dict
    error_message: str | None = None
    duration_ms: int | None = None
    created_at: datetime


class ReviewCreate(BaseModel):
    findings: str = Field(min_length=3, max_length=5000)
    impression: str = Field(min_length=3, max_length=2000)
    recommendation: str = Field(default="", max_length=2000)
    ai_agreement: ReviewAgreement
    status: ReviewStatus = ReviewStatus.draft
    analysis_id: int | None = None


class ReviewOut(ORM):
    id: int
    upload_id: int
    analysis_id: int | None
    doctor: UserBrief
    findings: str
    impression: str
    recommendation: str
    ai_agreement: ReviewAgreement
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime


class XrayOut(ORM):
    id: int
    owner_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    view_position: str | None = None
    patient_note: str | None = None
    status: UploadStatus
    created_at: datetime
    latest_analysis: AnalysisOut | None = None
    review_count: int = 0


class XrayDetail(XrayOut):
    owner: UserBrief
    analyses: list[AnalysisOut]
    reviews: list[ReviewOut]


class ModelStatusOut(BaseModel):
    available: bool
    state: str
    reason: str
    model_name: str | None = None
    model_version: str | None = None
    backend: str | None = None
    labels: list[str] = []
    score_type: str | None = None
    score_description: str | None = None
    weights_sha256: str | None = None
    device: str | None = None
    source: str | None = None


# ---------- clinical notes ----------
class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    visible_to_patient: bool = False


class NoteOut(ORM):
    id: int
    patient_id: int
    doctor: UserBrief
    body: str
    visible_to_patient: bool
    created_at: datetime


class PatientSummary(BaseModel):
    patient: UserOut
    assignment_id: int
    assigned_since: datetime | None
    xray_count: int
    pending_review_count: int
    next_appointment: datetime | None


class PatientRecord(BaseModel):
    patient: UserOut
    xrays: list[XrayOut]
    notes: list[NoteOut]
    appointments: list[AppointmentOut]


# ---------- admin ----------
class UserStatusUpdate(BaseModel):
    status: AccountStatus


class AuditOut(ORM):
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    detail: dict
    created_at: datetime


class AdminStats(BaseModel):
    patients: int
    doctors_approved: int
    doctors_pending: int
    assignments_pending: int
    appointments_upcoming: int
    xrays_total: int
    analyses_total: int
    model_available: bool
