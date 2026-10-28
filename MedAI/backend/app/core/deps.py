"""FastAPI dependencies for authentication and role-based authorization."""
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import AccountStatus, DoctorProfileStatus, RevokedToken, User, UserRole

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated or session expired. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)

# Endpoints a user with a temporary password may still call.
_PASSWORD_CHANGE_ALLOWED = {
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/change-password"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/logout-all"),
}


def get_token_claims(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(creds.credentials)
        int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED from None
    return payload


def get_current_user(
    request: Request,
    payload: dict = Depends(get_token_claims),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, int(payload["sub"]))
    # Reload on every request: disabled accounts and revoked tokens stop working immediately.
    if user is None or user.token_version != payload.get("tv") or user.role.value != payload.get("role"):
        raise _UNAUTHORIZED
    if db.get(RevokedToken, payload["jti"]) is not None:
        raise _UNAUTHORIZED
    if user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    if user.must_change_password and (request.method, request.url.path) not in _PASSWORD_CHANGE_ALLOWED:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Please change your temporary password before continuing (Account settings).")
    return user


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action.")
        return user
    return dependency


require_patient = require_roles(UserRole.patient)
require_doctor = require_roles(UserRole.doctor)
require_admin = require_roles(UserRole.admin)


def require_approved_doctor(user: User = Depends(require_doctor)) -> User:
    """Clinical endpoints require an administrator-approved doctor profile."""
    profile = user.doctor_profile
    if profile is None or profile.status != DoctorProfileStatus.approved:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your doctor profile must be approved by an administrator before you can access patient data.")
    return user
