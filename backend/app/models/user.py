import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole


class User(Base):
    """Identity + profile table. CoreFusion owns this record end-to-end —
    password hashing, sessions, email verification, and lockout are all
    application-controlled (see core/password.py, models/user_session.py,
    models/password_reset_token.py, models/email_verification_token.py).
    No external identity provider is the source of truth for any of this;
    `id` is a normal application-generated UUID, not tied to another
    system's user table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    avatar: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.guest, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Account lockout (brute-force/credential-stuffing defense — see
    # core auth service's login flow).
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # MFA/2FA (TOTP) — per-account opt-in, only usable at all when
    # settings.mfa_enabled is True (core/config.py). OFF by default for every
    # account; enabling this is entirely a user action via
    # POST /auth/mfa/setup + /auth/mfa/enable, never automatic.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(255))
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    employee_profile = relationship("Employee", back_populates="user", uselist=False)
    client_profile = relationship("Client", back_populates="user", uselist=False)
    partner_account = relationship("PartnerAccount", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    oauth_accounts = relationship("OAuthAccount", back_populates="user")
