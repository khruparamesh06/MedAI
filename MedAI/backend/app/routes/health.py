from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.schemas import ModelStatusOut
from app.services.ai import get_model_service

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    """Liveness: the process is up."""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "environment": s.app_env, "clinic_timezone": s.clinic_timezone}


@router.get("/api/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    """Readiness: the database is reachable. AI availability is reported but not required."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    model = get_model_service().status()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "model_state": model.state}


@router.get("/api/ai/status", response_model=ModelStatusOut, dependencies=[Depends(get_current_user)])
def model_status():
    return get_model_service().status().to_dict()
