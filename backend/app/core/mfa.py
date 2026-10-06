"""TOTP-based 2FA (RFC 6238), fully self-hosted — no external MFA/identity
provider. Gated entirely behind `settings.mfa_enabled` (see core/config.py);
this module works regardless, so the gate always lives at the router layer,
not here.

The TOTP secret must be stored reversibly (verifying a code requires the
original secret, not a hash of it) — Fernet (authenticated symmetric
encryption) is used for that, keyed by `settings.mfa_encryption_key`. This is
a different threat model from password/token storage: a password or session
token is either a human-chosen or purely-random secret we only ever need to
*compare against*, so a one-way hash (Argon2id / SHA-256, see
core/password.py and core/tokens.py) is correct there. A TOTP secret must be
recovered in full on every login, so encryption — not hashing — is the only
option.
"""
import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    if not settings.mfa_encryption_key:
        raise RuntimeError(
            "MFA_ENCRYPTION_KEY is not configured — required whenever MFA_ENABLED=true. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(settings.mfa_encryption_key.encode())


def generate_totp_secret() -> str:
    """A random base32 secret, suitable for any standard authenticator app."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("MFA secret could not be decrypted — MFA_ENCRYPTION_KEY may have changed") from exc


def provisioning_uri(secret: str, account_email: str) -> str:
    """An otpauth:// URI — the frontend renders this as a QR code (any
    client-side QR library) for the user to scan with an authenticator app.
    No QR image is generated server-side, keeping this module dependency-light."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=settings.mfa_issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """`valid_window=1` tolerates one 30s step of clock drift on either side —
    standard practice for TOTP verification, since phone/server clocks are
    never perfectly in sync."""
    code = (code or "").strip()
    if not code.isdigit():
        return False
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
