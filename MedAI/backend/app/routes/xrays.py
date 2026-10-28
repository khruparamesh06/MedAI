"""X-ray upload, private retrieval, AI analysis requests and clinician reviews."""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_approved_doctor, require_patient
from app.db.session import get_db
from app.models import (
    AnalysisResult, AnalysisStatus, ClinicalReview, ReviewStatus, UploadStatus, User, XrayUpload,
)
from app.routes.common import Pagination, paginate
from app.schemas import AnalysisOut, Page, ReviewCreate, ReviewOut, XrayDetail, XrayOut
from app.services import audit, rate_limit, storage
from app.services.access import get_accessible_upload, not_found
from app.services.ai import ImageNotSuitable, ModelUnavailable, get_model_service, open_image
from app.services.images import read_limited, validate_image
from app.services.serializers import analysis_out, xray_detail, xray_out

router = APIRouter(prefix="/api/xrays", tags=["x-rays"])
logger = logging.getLogger("medai.ai")


@router.post("", response_model=XrayOut, status_code=status.HTTP_201_CREATED)
async def upload_xray(
    file: UploadFile = File(..., description="PNG or JPEG chest X-ray"),
    view_position: Literal["PA", "AP", "lateral", "unknown"] = Form("unknown"),
    note: str = Form("", max_length=1000),
    patient: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    rate_limit.enforce(f"upload:{patient.id}", rate_limit.UPLOADS_PER_USER, rate_limit.HOURLY, "uploads")
    data = await read_limited(file, get_settings().max_upload_bytes)
    image = validate_image(data, file.filename)
    stored_name = storage.new_stored_name()
    storage.save(stored_name, image.png_bytes)
    upload = XrayUpload(
        owner_id=patient.id, original_filename=image.original_filename, stored_filename=stored_name,
        content_type="image/png", size_bytes=len(image.png_bytes), width=image.width, height=image.height,
        sha256=image.sha256, view_position=None if view_position == "unknown" else view_position,
        patient_note=note.strip() or None)
    db.add(upload)
    try:
        db.flush()
        audit.record(db, patient, "xray.uploaded", "xray", upload.id)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored_name)
        raise
    db.refresh(upload)
    return xray_out(upload, patient)


@router.get("", response_model=Page[XrayOut])
def my_xrays(page: Pagination = Depends(), patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    stmt = select(XrayUpload).where(XrayUpload.owner_id == patient.id).order_by(XrayUpload.created_at.desc())
    items, total = paginate(db, stmt, page)
    return Page(items=[xray_out(u, patient) for u in items], total=total, limit=page.limit, offset=page.offset)


@router.get("/{upload_id}", response_model=XrayDetail)
def get_xray(upload_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return xray_detail(get_accessible_upload(db, user, upload_id), user)


@router.get("/{upload_id}/image", response_class=FileResponse)
def get_xray_image(upload_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Streams the private image after the same authorization check as the record itself."""
    upload = get_accessible_upload(db, user, upload_id)
    try:
        path = storage.path_for(upload.stored_filename)
    except ValueError:
        raise not_found("Image") from None
    if not path.is_file():
        raise not_found("Image file")
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_xray(upload_id: int, patient: User = Depends(require_patient), db: Session = Depends(get_db)):
    upload = get_accessible_upload(db, patient, upload_id)
    if any(r.status == ReviewStatus.final for r in upload.reviews):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This X-ray has a finalised clinician review and is part of your medical record.")
    stored = upload.stored_filename
    audit.record(db, patient, "xray.deleted", "xray", upload.id)
    db.delete(upload)
    db.commit()
    storage.delete(stored)


@router.post("/{upload_id}/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def analyze_xray(upload_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Runs the configured model. If no genuine model is configured, responds 503 and records nothing:
    no result is ever produced without real inference.
    """
    upload = get_accessible_upload(db, user, upload_id)
    rate_limit.enforce(f"analyze:{user.id}", rate_limit.ANALYSES_PER_USER, rate_limit.HOURLY, "analysis requests")
    service = get_model_service()
    model = service.status()
    if not model.available:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Model not configured: {model.reason}")
    message = None
    try:
        image = open_image(storage.path_for(upload.stored_filename).read_bytes())
    except (OSError, ValueError, SyntaxError):  # missing/corrupted file (UnidentifiedImageError is an OSError)
        logger.error("stored image for upload %s could not be read", upload.id)
        message = "The stored image could not be read."
    else:
        try:
            prediction = service.predict(image)
        except ModelUnavailable as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Model not configured: {exc}") from None
        except ImageNotSuitable as exc:
            message = str(exc)
        except Exception:  # noqa: BLE001 - never crash or invent output; log details for operators only
            logger.exception("inference failed for upload %s", upload.id)
            message = "The model could not process this image. The error has been logged for the administrator."
    if message is not None:
        result = AnalysisResult(
            upload_id=upload.id, requested_by_id=user.id, status=AnalysisStatus.failed,
            model_name=model.model_name, model_version=model.model_version, weights_sha256=model.weights_sha256,
            score_type=model.score_type, findings=[], preprocessing={}, error_message=message)
        upload.status = UploadStatus.analysis_failed
    else:
        result = AnalysisResult(
            upload_id=upload.id, requested_by_id=user.id, status=AnalysisStatus.completed,
            model_name=model.model_name, model_version=model.model_version, weights_sha256=model.weights_sha256,
            score_type=model.score_type, findings=prediction.findings, preprocessing=prediction.preprocessing,
            duration_ms=prediction.duration_ms)
        upload.status = UploadStatus.analyzed
    db.add(result)
    db.flush()
    audit.record(db, user, f"analysis.{result.status.value}", "analysis", result.id, upload_id=upload.id)
    db.commit()
    db.refresh(result)
    return analysis_out(result)


# ----- clinician reviews -----
@router.post("/{upload_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(upload_id: int, body: ReviewCreate, doctor: User = Depends(require_approved_doctor),
                  db: Session = Depends(get_db)):
    upload = get_accessible_upload(db, doctor, upload_id)
    if body.analysis_id is not None and body.analysis_id not in {a.id for a in upload.analyses}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "analysis_id does not belong to this X-ray.")
    review = ClinicalReview(upload_id=upload.id, doctor_id=doctor.id, **body.model_dump())
    db.add(review)
    db.flush()
    audit.record(db, doctor, "review.created", "review", review.id, upload_id=upload.id, status=body.status.value)
    db.commit()
    db.refresh(review)
    return review


@router.put("/reviews/{review_id}", response_model=ReviewOut)
def update_review(review_id: int, body: ReviewCreate, doctor: User = Depends(require_approved_doctor),
                  db: Session = Depends(get_db)):
    review = db.get(ClinicalReview, review_id)
    if review is None or review.doctor_id != doctor.id:
        raise not_found("Review")
    get_accessible_upload(db, doctor, review.upload_id)  # assignment must still be active
    if review.status == ReviewStatus.final:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finalised reviews cannot be edited. Add a new review instead.")
    if body.analysis_id is not None and body.analysis_id not in {a.id for a in review.upload.analyses}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "analysis_id does not belong to this X-ray.")
    for key, value in body.model_dump().items():
        setattr(review, key, value)
    audit.record(db, doctor, "review.updated", "review", review.id, status=body.status.value)
    db.commit()
    return review
