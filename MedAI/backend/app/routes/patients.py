from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_patient
from app.db.session import get_db
from app.models import Appointment, ClinicalNote, User, XrayUpload
from app.schemas import AppointmentOut, NoteOut, PatientRecord, UserOut
from app.services.serializers import xray_out

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/me/record", response_model=PatientRecord)
def my_record(patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    """The patient's own medical record: uploads with results, shared notes, and appointments."""
    xrays = db.scalars(select(XrayUpload).where(XrayUpload.owner_id == patient.id)
                       .order_by(XrayUpload.created_at.desc()))
    notes = db.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == patient.id,
                                                  ClinicalNote.visible_to_patient.is_(True))
                       .order_by(ClinicalNote.created_at.desc()))
    appts = db.scalars(select(Appointment).where(Appointment.patient_id == patient.id)
                       .order_by(Appointment.scheduled_at.desc()))
    return PatientRecord(patient=UserOut.model_validate(patient), xrays=[xray_out(x, patient) for x in xrays],
                         notes=[NoteOut.model_validate(n) for n in notes],
                         appointments=[AppointmentOut.model_validate(a) for a in appts])
