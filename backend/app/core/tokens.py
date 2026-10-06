"""Opaque token generation/hashing — shared by sessions, password-reset, and
email-verification tokens.

Deliberately opaque (high-entropy random strings), not JWTs: a JWT's whole
value proposition is stateless verification, which is exactly what a
revocable, database-backed session needs to NOT have — you can't revoke a
stateless JWT before its own expiry without a separate revocation-list
lookup anyway, at which point you've built a database-backed session with
extra steps. An opaque token looked up by its hash in `user_sessions` (or
the matching reset/verification table) is simpler and matches this project's
KISS standard.

Hashing (not encrypting) the token before storage means a database
read/leak doesn't hand over usable credentials — SHA-256 is appropriate here
(not Argon2/bcrypt) because these tokens are already high-entropy random
values, not human-choosable passwords; the threat Argon2 defends against
(fast offline brute-force of a low-entropy secret) doesn't apply to a
256-bit random token.
"""
import hashlib
import secrets

TOKEN_BYTES = 32  # 256 bits of entropy


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
