from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_patient
from app.db.session import get_db
from app.models import (
    Appointment, AppointmentStatus, Assignment, AssignmentStatus, DoctorProfileStatus, User, UserRole,
)
from app.routes.common import Pagination, paginate
from app.schemas import AppointmentCreate, AppointmentOut, AppointmentStatusUpdate, Page
from app.services import audit
from app.services.access import can_access_patient, doctor_is_assigned

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

OPEN = (AppointmentStatus.requested, AppointmentStatus.confirmed)
MIN_LEAD = timedelta(hours=1)
MAX_AHEAD = timedelta(days=180)


def _as_aware(dt: datetime) -> datetime:
    # SQLite returns naive datetimes; values are always stored in UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _check_slot(db: Session, doctor: User, patient: User, start: datetime, minutes: int) -> None:
    now = datetime.now(timezone.utc)
    if start < now + MIN_LEAD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Appointments must be booked at least 1 hour ahead.")
    if start > now + MAX_AHEAD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Appointments can be booked at most 180 days ahead.")
    if start.minute % 15 or start.second or start.microsecond:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Start time must be on a 15-minute boundary.")
    end = start + timedelta(minutes=minutes)

    slots = doctor.doctor_profile.availability if doctor.doctor_profile else []
    if slots:
        tz = ZoneInfo(get_settings().clinic_timezone)
        local_start, local_end = start.astimezone(tz), end.astimezone(tz)
        fits = local_start.date() == local_end.date() and any(
            s.weekday == local_start.weekday() and s.start_time <= local_start.time()
            and local_end.time() <= s.end_time for s in slots)
        if not fits:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "The requested time is outside the doctor's availability.")

    window = (now - timedelta(days=1), end)
    for who, column in ((doctor, Appointment.doctor_id), (patient, Appointment.patient_id)):
        candidates = db.scalars(select(Appointment).where(
            column == who.id, Appointment.status.in_(OPEN),
            and_(Appointment.scheduled_at >= window[0], Appointment.scheduled_at < window[1])))
        for appt in candidates:
            a_start = _as_aware(appt.scheduled_at)
            if a_start < end and start < a_start + timedelta(minutes=appt.duration_minutes):
                whose = "The doctor already has" if who is doctor else "You already have"
                raise HTTPException(status.HTTP_409_CONFLICT, f"{whose} an appointment that overlaps this time.")


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def request_appointment(body: AppointmentCreate, patient: User = Depends(require_patient),
                        db: Session = Depends(get_db)):
    doctor = db.get(User, body.doctor_id)
    if doctor is None or doctor.role != UserRole.doctor or not doctor_is_assigned(db, doctor.id, patient.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You can only book appointments with a doctor who has been assigned to you.")
    tz = ZoneInfo(get_settings().clinic_timezone)
    start = datetime.combine(body.date, body.start_time, tzinfo=tz).astimezone(timezone.utc)
    _check_slot(db, doctor, patient, start, body.duration_minutes)
    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, scheduled_at=start,
                       duration_minutes=body.duration_minutes, reason=body.reason.strip())
    db.add(appt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This time slot has just been booked.") from None
    audit.record(db, patient, "appointment.requested", "appointment", appt.id, doctor_id=doctor.id)
    db.commit()
    db.refresh(appt)
    return appt


@router.get("", response_model=Page[AppointmentOut])
def list_appointments(page: Pagination = Depends(), status_filter: AppointmentStatus | None = Query(None, alias="status"),
                      upcoming: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Patients see their own; doctors see theirs; administrators see all."""
    stmt = select(Appointment)
    if user.role == UserRole.patient:
        stmt = stmt.where(Appointment.patient_id == user.id)
    elif user.role == UserRole.doctor:
        # Same rule as other clinical data: approved profile, and only currently assigned patients.
        if user.doctor_profile is None or user.doctor_profile.status != DoctorProfileStatus.approved:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Your doctor profile must be approved by an administrator before you can access patient data.")
        assigned = select(Assignment.patient_id).where(
            Assignment.doctor_id == user.id, Assignment.status == AssignmentStatus.approved)
        stmt = stmt.where(Appointment.doctor_id == user.id, Appointment.patient_id.in_(assigned))
    if status_filter:
        stmt = stmt.where(Appointment.status == status_filter)
    if upcoming:
        stmt = stmt.where(Appointment.scheduled_at >= datetime.now(timezone.utc), Appointment.status.in_(OPEN))
        stmt = stmt.order_by(Appointment.scheduled_at.asc())
    else:
        stmt = stmt.order_by(Appointment.scheduled_at.desc())
    items, total = paginate(db, stmt, page)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


# Allowed transitions per role: {current_status: {new_status, ...}}
TRANSITIONS = {
    UserRole.doctor: {
        AppointmentStatus.requested: {AppointmentStatus.confirmed, AppointmentStatus.declined},
        AppointmentStatus.confirmed: {AppointmentStatus.completed, AppointmentStatus.cancelled},
    },
    UserRole.patient: {
        AppointmentStatus.requested: {AppointmentStatus.cancelled},
        AppointmentStatus.confirmed: {AppointmentStatus.cancelled},
    },
    UserRole.admin: {
        AppointmentStatus.requested: {AppointmentStatus.cancelled},
        AppointmentStatus.confirmed: {AppointmentStatus.cancelled},
    },
}


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment_status(appointment_id: int, body: AppointmentStatusUpdate,
                              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    appt = db.get(Appointment, appointment_id)
    visible = appt is not None and (
        user.role == UserRole.admin
        or (user.role == UserRole.patient and appt.patient_id == user.id)
        or (user.role == UserRole.doctor and appt.doctor_id == user.id and can_access_patient(db, user, appt.patient_id)))
    if not visible:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")

    new = AppointmentStatus(body.status)
    if new not in TRANSITIONS[user.role].get(appt.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Cannot change an appointment from '{appt.status.value}' to '{new.value}'.")
    starts = _as_aware(appt.scheduled_at)
    if new == AppointmentStatus.completed and starts > datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_409_CONFLICT, "An appointment cannot be completed before it starts.")
    if user.role == UserRole.patient and starts <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_409_CONFLICT, "Past appointments cannot be cancelled.")
    appt.status = new
    if body.note is not None and user.role == UserRole.doctor:
        appt.doctor_note = body.note.strip() or None
    audit.record(db, user, f"appointment.{new.value}", "appointment", appt.id)
    db.commit()
    return appt
