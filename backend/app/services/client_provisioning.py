import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.core.password import hash_password
from app.core.tokens import generate_token, hash_token
from app.models.client import Client
from app.models.employee import Employee
from app.models.lead import Lead
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.email_service import send_password_reset_email, send_welcome_email

PASSWORD_RESET_TOKEN_TTL_HOURS = 1

# Extracted from app/routers/contracts.py (originally only reachable via
# contract signing) so app/routers/leads.py's explicit "Convert Lead to
# Client" action (the workflow doc's Phase 3 — conversion happens right
# after a successful lead evaluation, before any proposal/contract exists)
# can provision the same account the same way. Both call sites are safe to
# run more than once for the same lead: everything here is find-or-create.


async def get_or_create_client_user(db: AsyncSession, lead: Lead) -> tuple[User, bool]:
    """Finds the User row for this lead's email, or creates one — a local
    account, hashed random unusable password (the person sets their own via
    the password-set email `send_client_welcome` sends, never a plaintext
    password this backend generated).

    Returns `(user, created)` — `created` tells the caller whether this is a
    brand-new account (which needs a welcome/credentials email) or a reused
    existing one (which doesn't).
    """
    existing_user = (await db.execute(select(User).where(User.email == lead.email))).scalar_one_or_none()
    if existing_user is not None:
        return existing_user, False

    user = User(
        id=uuid.uuid4(),
        name=lead.contact_name,
        email=lead.email,
        password_hash=hash_password(secrets.token_urlsafe(32)),  # unusable placeholder; real one set via the reset link below
        phone=lead.phone,
        role="client",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, True


async def send_client_welcome(db: AsyncSession, user: User, lead: Lead) -> None:
    """Best-effort: issues a real, usable password-set link (the same
    mechanism as /auth/forgot-password) plus a separate welcome notification.
    Failures are logged, never raised — the account itself is already
    committed by the time this runs, so a delivery failure shouldn't undo it
    or fail the caller's request; an admin can always trigger another reset
    later even if both sends fail here."""
    try:
        token = generate_token()
        db.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=PASSWORD_RESET_TOKEN_TTL_HOURS),
        ))
        await db.commit()
        reset_url = f"{settings.client_url.rstrip('/')}/reset-password?token={token}"
        await send_password_reset_email(lead.contact_name, lead.email, reset_url)
    except Exception as exc:  # noqa: BLE001 — account provisioning must not fail over email delivery
        logger.warning("Failed to send password-reset email to %s: %s", lead.email, exc)
    try:
        await send_welcome_email(lead.contact_name, lead.email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send welcome email to %s: %s", lead.email, exc)


async def get_or_create_client_record(db: AsyncSession, user: User, lead: Lead) -> Client:
    """Finds the Client profile row for this user, or creates one — linked
    to the lead's owner's Employee record as account manager, if resolvable."""
    account_mgr_employee = None
    if lead.owner_id:
        account_mgr_employee = (await db.execute(select(Employee).where(Employee.user_id == lead.owner_id))).scalar_one_or_none()

    client = (await db.execute(select(Client).where(Client.user_id == user.id))).scalar_one_or_none()
    if client is not None:
        return client

    client = Client(
        user_id=user.id,
        company_name=lead.company,
        account_manager_id=account_mgr_employee.id if account_mgr_employee else None,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


async def provision_client_account(db: AsyncSession, lead: Lead) -> Client | None:
    """Orchestrates client provisioning for a newly-won lead: find-or-create
    the local User account (sending the welcome/password-set email only
    when that account is actually new), then find-or-create the linked
    Client profile."""
    user, created = await get_or_create_client_user(db, lead)
    if user is None:
        return None
    if created:
        await send_client_welcome(db, user, lead)
    return await get_or_create_client_record(db, user, lead)
