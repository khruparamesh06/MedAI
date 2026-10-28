from datetime import datetime, timedelta, timezone

import jwt

from app.models import AccountStatus, User, UserRole
from app.tests.conftest import PASSWORD, login, make_user

REG = {"email": "new@example.com", "password": "Sup3rSecret!", "full_name": "New Patient"}


def test_register_creates_patient_and_returns_token(client):
    r = client.post("/api/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "patient"
    assert body["token_type"] == "bearer"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "new@example.com"


def test_register_cannot_choose_role(client, db):
    r = client.post("/api/auth/register", json={**REG, "role": "admin"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "patient"
    assert db.query(User).filter(User.role == UserRole.admin).count() == 0


def test_duplicate_registration_is_rejected_case_insensitively(client):
    assert client.post("/api/auth/register", json=REG).status_code == 201
    r = client.post("/api/auth/register", json={**REG, "email": "NEW@example.com"})
    assert r.status_code == 409


def test_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={**REG, "password": "short"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={**REG, "password": "onlyletterslong"})
    assert r.status_code == 422


def test_password_is_hashed_with_argon2(client, db):
    client.post("/api/auth/register", json=REG)
    user = db.query(User).filter_by(email="new@example.com").one()
    assert user.password_hash.startswith("$argon2id$")
    assert REG["password"] not in user.password_hash


def test_login_success_and_failure(client, db):
    make_user(db, "p@example.com")
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": "WrongPass123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401


def test_missing_and_invalid_tokens(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    forged = jwt.encode({"sub": "1", "role": "admin", "tv": 0, "type": "access",
                         "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(client, db):
    from app.core.config import get_settings
    user = make_user(db, "p@example.com")
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    token = jwt.encode({"sub": str(user.id), "role": "patient", "tv": 0, "type": "access",
                        "iat": past, "exp": past + timedelta(minutes=5)}, get_settings().jwt_secret_key, "HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_disabled_account_cannot_login_or_use_token(client, db):
    user = make_user(db, "p@example.com")
    headers = login(client, "p@example.com")
    user.status = AccountStatus.disabled
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 403
    assert client.post("/api/auth/login", json={"email": "p@example.com", "password": PASSWORD}).status_code == 403


def test_logout_all_revokes_tokens(client, db):
    make_user(db, "p@example.com")
    headers = login(client, "p@example.com")
    assert client.post("/api/auth/logout-all", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_change_password(client, db):
    make_user(db, "p@example.com")
    headers = login(client, "p@example.com")
    r = client.post("/api/auth/change-password", headers=headers,
                    json={"current_password": PASSWORD, "new_password": "BrandNew456!"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401  # old token revoked
    login(client, "p@example.com", "BrandNew456!")


def test_role_restrictions(client, people):
    _, h = people
    assert client.get("/api/admin/stats", headers=h["pat"]).status_code == 403
    assert client.get("/api/admin/stats", headers=h["doc"]).status_code == 403
    assert client.get("/api/admin/stats", headers=h["admin"]).status_code == 200
    assert client.get("/api/doctor/patients", headers=h["pat"]).status_code == 403
    assert client.post("/api/xrays", headers=h["doc"], files={"file": ("a.png", b"x", "image/png")}).status_code == 403


def test_profile_update(client, people):
    _, h = people
    r = client.patch("/api/auth/me", headers=h["pat"], json={"phone": "+91 90000 00000", "sex": "female"})
    assert r.status_code == 200 and r.json()["phone"] == "+91 90000 00000"
    r = client.patch("/api/auth/me", headers=h["pat"], json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "patient"
