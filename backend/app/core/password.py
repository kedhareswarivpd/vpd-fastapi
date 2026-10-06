"""Password hashing for CoreFusion-owned authentication.

Argon2id (the OWASP-recommended default) via `argon2-cffi`, replacing
Supabase Auth's password handling entirely — CoreFusion now owns the
credential, not a third-party identity provider. Parameters follow
argon2-cffi's own "reasonably secure default for 2024+ hardware" profile
(19 MiB memory, 2 iterations, 1 parallelism lane — argon2-cffi's own
`PasswordHasher()` defaults, explicit here rather than implicit so a future
reader doesn't have to open the library source to know what's configured).
"""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,  # KiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:  # noqa: BLE001 — a malformed/foreign hash is a mismatch, not a crash
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the stored hash was made with older parameters than
    `_hasher`'s current ones — callers should re-hash and store the result
    the next time they have the plaintext password (i.e. right after a
    successful `verify_password`)."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:  # noqa: BLE001
        return False
