"""
Test fixtures. Every test runs against a fresh temporary SQLite database and a temporary upload
folder; only synthetic accounts and generated images are used.
"""
import io
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_TMP = Path(tempfile.mkdtemp(prefix="medai-tests-"))
_DISABLED_CFG = _TMP / "model_disabled.json"
_DISABLED_CFG.write_text(json.dumps({"enabled": False}))

os.environ.update({
    "APP_ENV": "test",
    "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-0123456789",
    # Set TEST_DATABASE_URL to run the suite against PostgreSQL (the database is emptied per test).
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "MODEL_CONFIG_PATH": str(_DISABLED_CFG),
    "MAX_UPLOAD_MB": "2",
    "CLINIC_TIMEZONE": "UTC",
})

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    DoctorAvailability, DoctorProfile, DoctorProfileStatus, User, UserRole,
)

PASSWORD = "TestPass123!"


@pytest.fixture(autouse=True)
def _fresh_db():
    from app.services.rate_limit import limiter
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    limiter.reset()  # rate limits stay enabled in tests, but each test starts with a clean slate
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def make_user(db, email, role=UserRole.patient, name="Test User", doctor_status=None, availability=True):
    user = User(email=email, full_name=name, role=role, password_hash=hash_password(PASSWORD))
    db.add(user)
    db.flush()
    if role == UserRole.doctor:
        profile = DoctorProfile(user_id=user.id, specialty="Radiology", license_number="LIC-123",
                                years_experience=5, status=doctor_status or DoctorProfileStatus.approved)
        db.add(profile)
        db.flush()
        if availability:
            from datetime import time
            for wd in range(7):
                db.add(DoctorAvailability(profile_id=profile.id, weekday=wd, start_time=time(0), end_time=time(23, 45)))
    db.commit()
    return user


def login(client, email, password=PASSWORD) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def people(client, db):
    """A standard cast: admin, two approved doctors, one pending doctor, two patients."""
    users = {
        "admin": make_user(db, "admin@example.com", UserRole.admin, "Admin"),
        "doc": make_user(db, "doc@example.com", UserRole.doctor, "Dr Approved"),
        "doc2": make_user(db, "doc2@example.com", UserRole.doctor, "Dr Other"),
        "pending_doc": make_user(db, "pending@example.com", UserRole.doctor, "Dr Pending",
                                 doctor_status=DoctorProfileStatus.pending),
        "pat": make_user(db, "pat@example.com", UserRole.patient, "Patient One"),
        "pat2": make_user(db, "pat2@example.com", UserRole.patient, "Patient Two"),
    }
    headers = {k: login(client, u.email) for k, u in users.items()}
    return users, headers


def png_bytes(size=(512, 512), mode="L", color=False) -> bytes:
    """Synthetic grayscale gradient image (not a medical image)."""
    w, h = size
    arr = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    if color:
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        rgb[..., 0] = 255
        rgb[..., 1] = arr
        img = Image.fromarray(rgb, "RGB")
    else:
        img = Image.fromarray(arr, "L").convert(mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def assign(client, people, patient="pat", doctor="doc"):
    users, h = people
    r = client.post("/api/assignments", json={"doctor_id": users[doctor].id, "reason": "test"}, headers=h[patient])
    assert r.status_code == 201, r.text
    r = client.post(f"/api/admin/assignments/{r.json()['id']}/approve", json={}, headers=h["admin"])
    assert r.status_code == 200, r.text
    return r.json()


def upload(client, headers, data=None, filename="chest.png"):
    return client.post("/api/xrays", files={"file": (filename, data or png_bytes(), "image/png")},
                       data={"view_position": "PA"}, headers=headers)
