from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_token_claims
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AccountStatus, RevokedToken, User, UserRole
from app.schemas import (
    ChangePasswordRequest, LoginRequest, Message, ProfileUpdate, RegisterRequest, TokenResponse, UserOut,
)
from app.services import audit, rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Pre-computed hash so failed logins for unknown emails take as long as wrong passwords.
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


def _token_response(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role.value, user.token_version)
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Public registration. Always creates a **patient** account; the role cannot be chosen."""
    rate_limit.enforce(f"register-ip:{rate_limit.client_ip(request)}", rate_limit.REGISTRATIONS_PER_IP,
                       rate_limit.REGISTRATION_WINDOW, "registrations from this network")
    email = body.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name,
                role=UserRole.patient, date_of_birth=body.date_of_birth, sex=body.sex, phone=body.phone)
    db.add(user)
    try:
        db.flush()
        audit.record(db, user, "user.registered", "user", user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.") from None
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    rate_limit.check_login_allowed(request, email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        rate_limit.record_login_failure(request, email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not verify_password(body.password, user.password_hash):
        rate_limit.record_login_failure(request, email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if user.status != AccountStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled. Contact the administrator.")
    rate_limit.record_login_success(email)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if user.role != UserRole.patient:
        # Demographic fields only apply to patients.
        data = {k: v for k, v in data.items() if k == "full_name"}
    for key, value in data.items():
        if key == "full_name" and not value:
            continue
        setattr(user, key, value)
    db.commit()
    return user


@router.post("/change-password", response_model=TokenResponse)
def change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    rate_limit.enforce(f"password-change:{user.id}", rate_limit.PASSWORD_CHANGES_PER_USER, rate_limit.HOURLY,
                       "password change attempts")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The new password must be different from the current one.")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version += 1  # sign out other sessions
    audit.record(db, user, "user.password_changed", "user", user.id)
    db.commit()
    return _token_response(user)


@router.post("/logout", response_model=Message)
def logout(claims: dict = Depends(get_token_claims), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Revoke the token used for this request (other sessions stay signed in)."""
    now = datetime.now(timezone.utc)
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))  # housekeeping
    db.add(RevokedToken(jti=claims["jti"], user_id=user.id,
                        expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc)))
    db.commit()
    return Message(detail="Signed out.")


@router.post("/logout-all", response_model=Message)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invalidate every token issued to this account (the client should also discard its token)."""
    user.token_version += 1
    db.commit()
    return Message(detail="All sessions have been signed out.")
