"""
Central authorization rules for patient data. Every route that touches a patient's records
goes through these helpers so the rules are enforced consistently on the backend.

Rules:
  * a patient may access only their own records;
  * a doctor may access a patient's records only with an *approved* assignment and an approved profile;
  * administrators manage workflow and accounts but do not read clinical images or results.
Resources the caller may not see are reported as 404 so IDs cannot be probed.
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Assignment, AssignmentStatus, DoctorProfileStatus, User, UserRole, XrayUpload,
)


def not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def doctor_is_assigned(db: Session, doctor_id: int, patient_id: int) -> bool:
    return db.scalar(
        select(Assignment.id).where(
            Assignment.doctor_id == doctor_id,
            Assignment.patient_id == patient_id,
            Assignment.status == AssignmentStatus.approved,
        )
    ) is not None


def can_access_patient(db: Session, user: User, patient_id: int) -> bool:
    if user.role == UserRole.patient:
        return user.id == patient_id
    if user.role == UserRole.doctor:
        profile = user.doctor_profile
        return bool(profile and profile.status == DoctorProfileStatus.approved
                    and doctor_is_assigned(db, user.id, patient_id))
    return False


def get_accessible_upload(db: Session, user: User, upload_id: int) -> XrayUpload:
    upload = db.get(XrayUpload, upload_id)
    if upload is None or not can_access_patient(db, user, upload.owner_id):
        raise not_found("X-ray")
    return upload


def get_assigned_patient(db: Session, doctor: User, patient_id: int) -> User:
    patient = db.get(User, patient_id)
    if patient is None or patient.role != UserRole.patient or not can_access_patient(db, doctor, patient_id):
        raise not_found("Patient")
    return patient
