import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MfaBackupCode(Base):
    """One-time-use recovery codes issued when a user enables MFA, for the
    case their authenticator device is lost. Stored hashed (SHA-256, same
    justification as UserSession/PasswordResetToken in core/tokens.py — these
    are server-generated random values, not user-chosen secrets) — the
    plaintext codes are shown to the user exactly once, at generation time,
    and never stored or retrievable again."""

    __tablename__ = "mfa_backup_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User")
