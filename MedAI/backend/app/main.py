"""MedAI FastAPI application entry point.  Run: uvicorn app.main:app --reload"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.middleware import BodySizeLimitMiddleware
from app.routes import (
    admin, appointments, assignments, auth, doctor_portal, doctors, health, patients, xrays,
)
from app.services.ai import get_model_service

logger = logging.getLogger("medai")


def _configure_logging() -> None:
    # Operational logs only: never log passwords, tokens, image contents or clinical text.
    root = logging.getLogger("medai")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the model in the background so the first analysis request is not slowed down
    # and startup is not blocked when PyTorch takes a few seconds to import.
    def preload():
        status = get_model_service().status()
        logger.info("AI model state: %s %s", status.state, status.reason or status.model_version or "")
    threading.Thread(target=preload, name="model-preload", daemon=True).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging()
    docs = settings.api_docs_enabled
    app = FastAPI(
        title="MedAI API",
        version="1.1.0",
        description=(
            "AI-assisted chest X-ray analysis and hospital management API.\n\n"
            "**MedAI is an experimental decision-support tool. Model outputs are not diagnoses.**"),
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    # Order matters: the last middleware added runs first. CORS is outermost so that even 413
    # responses from the size limit carry CORS headers and the browser can show the real error.
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=settings.max_json_body_kb * 1024,
        upload_limit=settings.max_upload_bytes + 256 * 1024,  # multipart framing overhead
        upload_paths=("/api/xrays",),
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")  # API responses contain personal data
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # bearer tokens are sent in the Authorization header, not cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Return field locations and messages only: never echo submitted values (e.g. passwords).
        errors = [{"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred."})

    for module in (health, auth, patients, doctors, assignments, xrays, appointments, doctor_portal, admin):
        app.include_router(module.router)
    return app


app = create_app()
