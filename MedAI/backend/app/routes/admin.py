"""Administrator endpoints. Every route requires role=admin (enforced by the router dependency)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models import (
    AccountStatus, AnalysisResult, Appointment, AppointmentStatus, Assignment, AssignmentStatus, AuditEvent,
    DoctorProfile, DoctorProfileStatus, User, UserRole, XrayUpload,
)
from app.routes.common import Pagination, paginate
from app.schemas import (
    AdminStats, AssignmentOut, AuditOut, DoctorAdminOut, DoctorCreateRequest, DoctorProfileOut, Page,
    ReviewDecision, UserOut, UserStatusUpdate,
)
from app.services import audit
from app.services.ai import get_model_service

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db)):
    def count(stmt):
        return db.scalar(stmt) or 0
    now = datetime.now(timezone.utc)
    return AdminStats(
        patients=count(select(func.count(User.id)).where(User.role == UserRole.patient)),
        doctors_approved=count(select(func.count(DoctorProfile.id)).where(DoctorProfile.status == DoctorProfileStatus.approved)),
        doctors_pending=count(select(func.count(DoctorProfile.id)).where(DoctorProfile.status == DoctorProfileStatus.pending)),
        assignments_pending=count(select(func.count(Assignment.id)).where(Assignment.status == AssignmentStatus.pending)),
        appointments_upcoming=count(select(func.count(Appointment.id)).where(
            Appointment.scheduled_at >= now,
            Appointment.status.in_((AppointmentStatus.requested, AppointmentStatus.confirmed)))),
        xrays_total=count(select(func.count(XrayUpload.id))),
        analyses_total=count(select(func.count(AnalysisResult.id))),
        model_available=get_model_service().status().available,
    )


# ----- users -----
@router.get("/users", response_model=Page[UserOut])
def list_users(page: Pagination = Depends(), role: UserRole | None = None, q: str | None = Query(None, max_length=100),
               db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    items, total = paginate(db, stmt, page)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.patch("/users/{user_id}/status", response_model=UserOut)
def set_user_status(user_id: int, body: UserStatusUpdate, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot change the status of your own account.")
    if user.status != body.status:
        user.status = body.status
        user.token_version += 1  # revoke existing sessions
        audit.record(db, admin, f"user.{body.status.value}", "user", user.id)
        db.commit()
    return user


# ----- doctors -----
@router.post("/doctors", response_model=DoctorAdminOut, status_code=status.HTTP_201_CREATED)
def create_doctor(body: DoctorCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Create a doctor account. The doctor then signs in, completes the profile and submits it for approval."""
    email = body.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, full_name=body.full_name.strip(), role=UserRole.doctor,
                password_hash=hash_password(body.temporary_password), must_change_password=True)
    user.doctor_profile = DoctorProfile()
    db.add(user)
    db.flush()
    audit.record(db, admin, "doctor.account_created", "user", user.id)
    db.commit()
    db.refresh(user)
    return DoctorAdminOut(user=UserOut.model_validate(user), profile=DoctorProfileOut.model_validate(user.doctor_profile))


@router.get("/doctors", response_model=list[DoctorAdminOut])
def list_doctor_profiles(status_filter: DoctorProfileStatus | None = Query(None, alias="status"),
                         db: Session = Depends(get_db)):
    stmt = select(DoctorProfile).join(DoctorProfile.user).order_by(DoctorProfile.submitted_at.desc(), User.full_name)
    if status_filter:
        stmt = stmt.where(DoctorProfile.status == status_filter)
    return [DoctorAdminOut(user=UserOut.model_validate(p.user), profile=DoctorProfileOut.model_validate(p))
            for p in db.scalars(stmt)]


def _decide_profile(profile_id: int, approve: bool, body: ReviewDecision, admin: User, db: Session) -> DoctorProfileOut:
    profile = db.get(DoctorProfile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor profile not found")
    if profile.status != DoctorProfileStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only pending profiles can be reviewed (current: {profile.status.value}).")
    if not approve and not (body.note and body.note.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please give a reason for the rejection.")
    profile.status = DoctorProfileStatus.approved if approve else DoctorProfileStatus.rejected
    profile.review_note = (body.note or "").strip() or None
    profile.reviewed_by_id = admin.id
    profile.reviewed_at = utcnow()
    audit.record(db, admin, f"doctor_profile.{profile.status.value}", "doctor_profile", profile.id,
                 doctor_id=profile.user_id)
    db.commit()
    return DoctorProfileOut.model_validate(profile)


@router.post("/doctors/{profile_id}/approve", response_model=DoctorProfileOut)
def approve_doctor(profile_id: int, body: ReviewDecision = ReviewDecision(), admin: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return _decide_profile(profile_id, True, body, admin, db)


@router.post("/doctors/{profile_id}/reject", response_model=DoctorProfileOut)
def reject_doctor(profile_id: int, body: ReviewDecision, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return _decide_profile(profile_id, False, body, admin, db)


# ----- assignments -----
@router.get("/assignments", response_model=Page[AssignmentOut])
def list_assignments(page: Pagination = Depends(), status_filter: AssignmentStatus | None = Query(None, alias="status"),
                     db: Session = Depends(get_db)):
    stmt = select(Assignment).order_by(Assignment.created_at.desc())
    if status_filter:
        stmt = stmt.where(Assignment.status == status_filter)
    items, total = paginate(db, stmt, page)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


def _get_assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return assignment


@router.post("/assignments/{assignment_id}/approve", response_model=AssignmentOut)
def approve_assignment(assignment_id: int, body: ReviewDecision = ReviewDecision(),
                       admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if a.status != AssignmentStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only pending requests can be approved (current: {a.status.value}).")
    doctor = a.doctor
    if (doctor.status != AccountStatus.active or doctor.doctor_profile is None
            or doctor.doctor_profile.status != DoctorProfileStatus.approved):
        raise HTTPException(status.HTTP_409_CONFLICT, "The doctor is no longer approved or active.")
    if a.patient.status != AccountStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "The patient account is disabled.")
    a.status = AssignmentStatus.approved
    a.decision_note = (body.note or "").strip() or None
    a.decided_by_id, a.decided_at = admin.id, utcnow()
    audit.record(db, admin, "assignment.approved", "assignment", a.id)
    db.commit()
    return a


@router.post("/assignments/{assignment_id}/reject", response_model=AssignmentOut)
def reject_assignment(assignment_id: int, body: ReviewDecision, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if a.status != AssignmentStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only pending requests can be rejected (current: {a.status.value}).")
    a.status = AssignmentStatus.rejected
    a.decision_note = (body.note or "").strip() or None
    a.decided_by_id, a.decided_at = admin.id, utcnow()
    audit.record(db, admin, "assignment.rejected", "assignment", a.id)
    db.commit()
    return a


@router.post("/assignments/{assignment_id}/end", response_model=AssignmentOut)
def end_assignment(assignment_id: int, body: ReviewDecision = ReviewDecision(),
                   admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = _get_assignment(db, assignment_id)
    if a.status != AssignmentStatus.approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only approved assignments can be ended.")
    a.status = AssignmentStatus.ended
    a.decision_note = (body.note or "").strip() or a.decision_note
    a.decided_by_id, a.decided_at = admin.id, utcnow()
    # The doctor loses access, so open future appointments between the pair are cancelled.
    open_appts = db.scalars(select(Appointment).where(
        Appointment.patient_id == a.patient_id, Appointment.doctor_id == a.doctor_id,
        Appointment.status.in_((AppointmentStatus.requested, AppointmentStatus.confirmed)),
        Appointment.scheduled_at >= datetime.now(timezone.utc)))
    cancelled = 0
    for appt in open_appts:
        appt.status = AppointmentStatus.cancelled
        appt.doctor_note = "Cancelled automatically because the care assignment ended."
        cancelled += 1
    audit.record(db, admin, "assignment.ended", "assignment", a.id, appointments_cancelled=cancelled)
    db.commit()
    return a


# ----- audit -----
@router.get("/audit", response_model=Page[AuditOut])
def audit_log(page: Pagination = Depends(), action: str | None = Query(None, max_length=64),
              db: Session = Depends(get_db)):
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    items, total = paginate(db, stmt, page)
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)
