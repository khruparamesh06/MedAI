"""Clinical endpoints for approved doctors. Every query is scoped to approved assignments."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.deps import require_approved_doctor
from app.db.session import get_db
from app.models import (
    Appointment, AppointmentStatus, Assignment, AssignmentStatus, ClinicalNote, ClinicalReview,
    ReviewStatus, User, XrayUpload,
)
from app.schemas import (
    AppointmentOut, NoteCreate, NoteOut, PatientRecord, PatientSummary, UserOut, XrayOut,
)
from app.services import audit
from app.services.access import get_assigned_patient
from app.services.serializers import xray_out

router = APIRouter(prefix="/api/doctor", tags=["doctor portal"])

_final_review_exists = exists().where(
    ClinicalReview.upload_id == XrayUpload.id, ClinicalReview.status == ReviewStatus.final)


@router.get("/patients", response_model=list[PatientSummary])
def assigned_patients(doctor: User = Depends(require_approved_doctor), db: Session = Depends(get_db)):
    assignments = db.scalars(select(Assignment).where(
        Assignment.doctor_id == doctor.id, Assignment.status == AssignmentStatus.approved)
        .order_by(Assignment.decided_at.desc()))
    now = datetime.now(timezone.utc)
    result = []
    for a in assignments:
        xray_count = db.scalar(select(func.count(XrayUpload.id)).where(XrayUpload.owner_id == a.patient_id)) or 0
        pending = db.scalar(select(func.count(XrayUpload.id)).where(
            XrayUpload.owner_id == a.patient_id, ~_final_review_exists)) or 0
        next_appt = db.scalar(select(func.min(Appointment.scheduled_at)).where(
            Appointment.patient_id == a.patient_id, Appointment.doctor_id == doctor.id,
            Appointment.scheduled_at >= now,
            Appointment.status.in_((AppointmentStatus.requested, AppointmentStatus.confirmed))))
        result.append(PatientSummary(patient=UserOut.model_validate(a.patient), assignment_id=a.id,
                                     assigned_since=a.decided_at, xray_count=xray_count,
                                     pending_review_count=pending, next_appointment=next_appt))
    return result


@router.get("/review-queue", response_model=list[XrayOut])
def review_queue(doctor: User = Depends(require_approved_doctor), db: Session = Depends(get_db)):
    """X-rays of assigned patients that do not yet have a finalised clinician review."""
    assigned_ids = select(Assignment.patient_id).where(
        Assignment.doctor_id == doctor.id, Assignment.status == AssignmentStatus.approved)
    uploads = db.scalars(select(XrayUpload).where(XrayUpload.owner_id.in_(assigned_ids), ~_final_review_exists)
                         .order_by(XrayUpload.created_at.asc()).limit(50))
    return [xray_out(u, doctor) for u in uploads]


@router.get("/patients/{patient_id}", response_model=PatientRecord)
def patient_record(patient_id: int, doctor: User = Depends(require_approved_doctor), db: Session = Depends(get_db)):
    patient = get_assigned_patient(db, doctor, patient_id)
    xrays = db.scalars(select(XrayUpload).where(XrayUpload.owner_id == patient.id)
                       .order_by(XrayUpload.created_at.desc()))
    notes = db.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == patient.id)
                       .order_by(ClinicalNote.created_at.desc()))
    appts = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id,
                                                 Appointment.doctor_id == doctor.id)
                       .order_by(Appointment.scheduled_at.desc()))
    return PatientRecord(patient=UserOut.model_validate(patient), xrays=[xray_out(x, doctor) for x in xrays],
                         notes=[NoteOut.model_validate(n) for n in notes],
                         appointments=[AppointmentOut.model_validate(a) for a in appts])


@router.post("/patients/{patient_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(patient_id: int, body: NoteCreate, doctor: User = Depends(require_approved_doctor),
             db: Session = Depends(get_db)):
    patient = get_assigned_patient(db, doctor, patient_id)
    note = ClinicalNote(patient_id=patient.id, doctor_id=doctor.id, body=body.body.strip(),
                        visible_to_patient=body.visible_to_patient)
    db.add(note)
    db.flush()
    audit.record(db, doctor, "note.created", "clinical_note", note.id, patient_id=patient.id)
    db.commit()
    db.refresh(note)
    return note
