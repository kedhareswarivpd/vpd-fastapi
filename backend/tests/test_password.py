"""Unit tests for CoreFusion-owned password hashing (Argon2id) — replaces
the deleted Supabase JWT/JWKS test suite (tests/test_security.py) now that
identity verification is local, not a third-party token-verification call."""

from app.core.password import hash_password, needs_rehash, verify_password


class TestHashPassword:
    def test_produces_an_argon2id_hash(self):
        hashed = hash_password("correct horse battery staple")
        assert hashed.startswith("$argon2id$")

    def test_same_password_hashes_differently_each_time(self):
        """A fresh random salt per call — two hashes of the same password
        must never be equal (rules out a fixed-salt implementation bug)."""
        a = hash_password("same-password")
        b = hash_password("same-password")
        assert a != b


class TestVerifyPassword:
    def test_correct_password_verifies(self):
        hashed = hash_password("my-real-password")
        assert verify_password("my-real-password", hashed) is True

    def test_wrong_password_does_not_verify(self):
        hashed = hash_password("my-real-password")
        assert verify_password("wrong-password", hashed) is False

    def test_malformed_hash_does_not_verify_or_raise(self):
        assert verify_password("anything", "not-a-real-hash") is False

    def test_empty_hash_does_not_verify_or_raise(self):
        assert verify_password("anything", "") is False


class TestNeedsRehash:
    def test_freshly_hashed_password_does_not_need_rehash(self):
        hashed = hash_password("some-password")
        assert needs_rehash(hashed) is False

    def test_malformed_hash_reports_no_rehash_needed_rather_than_raising(self):
        assert needs_rehash("not-a-real-hash") is False
