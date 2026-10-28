"""Doctor directory (for patients) and the doctor's own profile/availability management."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_doctor
from app.db.base import utcnow
from app.db.session import get_db
from app.models import AccountStatus, DoctorAvailability, DoctorProfile, DoctorProfileStatus, User
from app.routes.common import Pagination, paginate
from app.schemas import (
    AvailabilitySlot, AvailabilityUpdate, DoctorProfileOut, DoctorProfileUpdate, DoctorPublic, Page,
)
from app.services import audit

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


def _public(profile: DoctorProfile) -> DoctorPublic:
    return DoctorPublic(
        user_id=profile.user_id, full_name=profile.user.full_name, specialty=profile.specialty,
        years_experience=profile.years_experience, bio=profile.bio, clinic_location=profile.clinic_location,
        availability=[AvailabilitySlot.model_validate(a) for a in profile.availability])


def _approved_query():
    return (select(DoctorProfile).join(DoctorProfile.user)
            .where(DoctorProfile.status == DoctorProfileStatus.approved, User.status == AccountStatus.active)
            .options(selectinload(DoctorProfile.user), selectinload(DoctorProfile.availability)))


@router.get("", response_model=Page[DoctorPublic], dependencies=[Depends(get_current_user)])
def list_doctors(page: Pagination = Depends(), q: str | None = Query(None, max_length=100),
                 specialty: str | None = Query(None, max_length=120), db: Session = Depends(get_db)):
    """Directory of **approved, active** doctors only."""
    stmt = _approved_query().order_by(User.full_name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), DoctorProfile.specialty.ilike(like)))
    if specialty:
        stmt = stmt.where(DoctorProfile.specialty.ilike(specialty.strip()))
    items, total = paginate(db, stmt, page)
    return Page(items=[_public(p) for p in items], total=total, limit=page.limit, offset=page.offset)


@router.get("/specialties", response_model=list[str], dependencies=[Depends(get_current_user)])
def list_specialties(db: Session = Depends(get_db)):
    rows = db.scalars(select(DoctorProfile.specialty).join(DoctorProfile.user)
                      .where(DoctorProfile.status == DoctorProfileStatus.approved,
                             User.status == AccountStatus.active).distinct())
    return sorted({r for r in rows if r})


# ----- the signed-in doctor's own profile (declared before /{doctor_id}) -----
def _own_profile(user: User, db: Session) -> DoctorProfile:
    if user.doctor_profile is None:
        user.doctor_profile = DoctorProfile(user_id=user.id)
        db.commit()
        db.refresh(user)
    return user.doctor_profile


@router.get("/me/profile", response_model=DoctorProfileOut)
def get_my_profile(user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    return _own_profile(user, db)


@router.put("/me/profile", response_model=DoctorProfileOut)
def update_my_profile(body: DoctorProfileUpdate, user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    profile = _own_profile(user, db)
    credentials_changed = (body.license_number != profile.license_number or body.specialty != profile.specialty)
    for key, value in body.model_dump().items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    if profile.status == DoctorProfileStatus.approved and credentials_changed:
        # Changing credentials of an approved profile requires a fresh administrator review.
        profile.status = DoctorProfileStatus.pending
        profile.submitted_at = utcnow()
        audit.record(db, user, "doctor_profile.resubmitted", "doctor_profile", profile.id)
    db.commit()
    return profile


@router.put("/me/availability", response_model=DoctorProfileOut)
def update_my_availability(body: AvailabilityUpdate, user: User = Depends(require_doctor),
                           db: Session = Depends(get_db)):
    profile = _own_profile(user, db)
    profile.availability.clear()
    db.flush()
    for slot in body.slots:
        profile.availability.append(DoctorAvailability(weekday=slot.weekday, start_time=slot.start_time,
                                                       end_time=slot.end_time))
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/me/profile/submit", response_model=DoctorProfileOut)
def submit_my_profile(user: User = Depends(require_doctor), db: Session = Depends(get_db)):
    profile = _own_profile(user, db)
    if profile.status not in (DoctorProfileStatus.draft, DoctorProfileStatus.rejected):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Profile is already {profile.status.value}.")
    if len(profile.specialty) < 2 or len(profile.license_number) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Please complete your specialty and license number before submitting.")
    profile.status = DoctorProfileStatus.pending
    profile.submitted_at = utcnow()
    profile.review_note = None
    audit.record(db, user, "doctor_profile.submitted", "doctor_profile", profile.id)
    db.commit()
    return profile


@router.get("/{doctor_id}", response_model=DoctorPublic, dependencies=[Depends(get_current_user)])
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    profile = db.scalar(_approved_query().where(DoctorProfile.user_id == doctor_id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return _public(profile)
