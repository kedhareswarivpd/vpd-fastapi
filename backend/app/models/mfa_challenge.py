import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MfaChallenge(Base):
    """A short-lived, single-use handoff token between "password verified"
    and "TOTP/backup code verified" for an MFA-enabled account. Login does
    NOT create a real session (UserSession) until the second factor is
    confirmed — this table's row is the only thing that exists in between,
    and it is deliberately not a session itself (it authenticates nothing on
    its own, cannot access any protected endpoint, and expires in minutes)."""

    __tablename__ = "mfa_challenges"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User")
