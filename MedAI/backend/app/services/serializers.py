"""Helpers that turn ORM objects into response schemas with computed fields."""
from app.models import AnalysisResult, ReviewStatus, User, UserRole, XrayUpload
from app.schemas import AnalysisOut, ReviewOut, XrayDetail, XrayOut
from app.services.ai import describe_score


def analysis_out(a: AnalysisResult) -> AnalysisOut:
    out = AnalysisOut.model_validate(a)
    out.score_description = describe_score(a.score_type)
    return out


def _visible_reviews(upload: XrayUpload, viewer: User):
    # Patients only see finalised reviews; doctors see final reviews plus their own drafts.
    for r in upload.reviews:
        if r.status == ReviewStatus.final or (viewer.role == UserRole.doctor and r.doctor_id == viewer.id):
            yield r


def xray_out(upload: XrayUpload, viewer: User) -> XrayOut:
    out = XrayOut.model_validate(upload)
    out.latest_analysis = analysis_out(upload.analyses[0]) if upload.analyses else None
    out.review_count = sum(1 for r in upload.reviews if r.status == ReviewStatus.final)
    return out


def xray_detail(upload: XrayUpload, viewer: User) -> XrayDetail:
    base = xray_out(upload, viewer).model_dump()
    return XrayDetail(
        **base,
        owner=upload.owner,
        analyses=[analysis_out(a) for a in upload.analyses],
        reviews=[ReviewOut.model_validate(r) for r in _visible_reviews(upload, viewer)],
    )
