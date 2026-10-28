"""Patient-side doctor assignment requests. Administrator decisions live in routes/admin.py."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_patient
from app.db.base import utcnow
from app.db.session import get_db
from app.models import (
    AccountStatus, Assignment, AssignmentStatus, DoctorProfileStatus, User, UserRole,
)
from app.schemas import AssignmentCreate, AssignmentOut
from app.services import audit

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

MAX_ACTIVE_ASSIGNMENTS = 5
ACTIVE = (AssignmentStatus.pending, AssignmentStatus.approved)


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def request_assignment(body: AssignmentCreate, patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    doctor = db.get(User, body.doctor_id)
    if (doctor is None or doctor.role != UserRole.doctor or doctor.status != AccountStatus.active
            or doctor.doctor_profile is None or doctor.doctor_profile.status != DoctorProfileStatus.approved):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found or not currently accepting patients.")

    existing = db.scalar(select(Assignment).where(
        Assignment.patient_id == patient.id, Assignment.doctor_id == doctor.id, Assignment.status.in_(ACTIVE)))
    if existing:
        msg = ("You already have a pending request with this doctor."
               if existing.status == AssignmentStatus.pending else "This doctor is already assigned to you.")
        raise HTTPException(status.HTTP_409_CONFLICT, msg)

    active_count = db.scalar(select(func.count(Assignment.id)).where(
        Assignment.patient_id == patient.id, Assignment.status.in_(ACTIVE))) or 0
    if active_count >= MAX_ACTIVE_ASSIGNMENTS:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"You can have at most {MAX_ACTIVE_ASSIGNMENTS} active doctor requests/assignments.")

    assignment = Assignment(patient_id=patient.id, doctor_id=doctor.id, request_reason=body.reason.strip())
    db.add(assignment)
    try:
        db.flush()
    except IntegrityError:  # concurrent duplicate caught by the partial unique index
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an active request with this doctor.") from None
    audit.record(db, patient, "assignment.requested", "assignment", assignment.id, doctor_id=doctor.id)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/mine", response_model=list[AssignmentOut])
def my_assignments(status_filter: AssignmentStatus | None = Query(None, alias="status"),
                   patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    stmt = select(Assignment).where(Assignment.patient_id == patient.id).order_by(Assignment.created_at.desc())
    if status_filter:
        stmt = stmt.where(Assignment.status == status_filter)
    return list(db.scalars(stmt))


@router.post("/{assignment_id}/cancel", response_model=AssignmentOut)
def cancel_assignment(assignment_id: int, patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    assignment = db.get(Assignment, assignment_id)
    if assignment is None or assignment.patient_id != patient.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment request not found")
    if assignment.status != AssignmentStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only pending requests can be withdrawn.")
    assignment.status = AssignmentStatus.cancelled
    assignment.decided_at = utcnow()
    audit.record(db, patient, "assignment.cancelled", "assignment", assignment.id)
    db.commit()
    return assignment
