import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import TimestampedRead


def _validate_password_complexity(value: str) -> str:
    """Shared policy for every password field below: length is enforced by
    Field(min_length=8), this adds the character-class requirements — at
    least one uppercase, one lowercase, one digit, and one symbol — so a
    password like "aaaaaaaa" (technically 8 chars) is rejected."""
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("Password must contain at least one special character")
    return value


class RegisterRequest(BaseModel):
    """
    Public self-serve signup is intentionally Client-only — there is no `role`
    field here. Employee/Admin/HR accounts are provisioned by an authenticated
    Admin/HR user via `POST /users` (see routers/users.py), never self-selected
    by an anonymous caller. Do not add `role` back here without an auth gate.
    """

    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None

    _validate_password = field_validator("password")(_validate_password_complexity)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)

    _validate_password = field_validator("password")(_validate_password_complexity)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _validate_new_password = field_validator("new_password")(_validate_password_complexity)


class UserRead(TimestampedRead):
    name: str
    email: EmailStr
    phone: str | None = None
    avatar: str | None = None
    role: UserRole
    is_active: bool
    is_email_verified: bool


class LoginResponse(BaseModel):
    """Tokens are never returned in the body — they travel as httpOnly
    cookies only (see core/cookies.py). The frontend never needs to see or
    store either token itself."""

    user: UserRead


class MfaChallengeResponse(BaseModel):
    """Returned by POST /auth/login instead of LoginResponse when the account
    has MFA enabled — no session cookies are set yet. The frontend must
    collect a TOTP/backup code from the user and call
    POST /auth/mfa/verify-login with this token to actually complete login."""

    mfa_required: bool = True
    mfa_token: str


class MfaVerifyLoginRequest(BaseModel):
    mfa_token: str | None = None  # falls back to the cf_mfa_pending_token cookie (set by the OAuth callback) if omitted
    code: str = Field(min_length=4, max_length=64)


class MfaSetupResponse(BaseModel):
    """`secret` is shown as a fallback for manual entry; `otpauth_url` is
    what the frontend renders as a QR code (any client-side QR library) for
    scanning with an authenticator app. Neither is usable to log in on its
    own — POST /auth/mfa/enable with a real generated code is still required
    to actually turn MFA on."""

    secret: str
    otpauth_url: str


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaEnableResponse(BaseModel):
    """`backup_codes` are shown in full exactly once, here — they are never
    retrievable again after this response (only their hashes are stored)."""

    backup_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str


class MfaStatusResponse(BaseModel):
    available: bool  # whether settings.mfa_enabled (the global switch) is on
    enabled: bool  # whether this specific account has turned MFA on
    enabled_at: datetime | None = None


class RegenerateBackupCodesRequest(BaseModel):
    password: str


class RegenerateBackupCodesResponse(BaseModel):
    backup_codes: list[str]


class SessionOut(BaseModel):
    id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    is_current: bool
