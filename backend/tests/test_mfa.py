"""Unit tests for app/core/mfa.py — TOTP secret generation/encryption and
code verification. No DB, no HTTP; pure function-level tests, following the
same pattern as test_password.py/test_tokens.py."""
import time

import pyotp
import pytest

from app.core import mfa


@pytest.fixture(autouse=True)
def _mfa_key(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setattr(mfa.settings, "mfa_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(mfa.settings, "mfa_issuer", "CoreFusion Technologies")


class TestSecretEncryption:
    def test_generated_secret_is_valid_base32(self):
        secret = mfa.generate_totp_secret()
        assert len(secret) >= 16
        pyotp.totp.TOTP(secret)  # raises if not valid base32

    def test_encrypt_then_decrypt_round_trips(self):
        secret = mfa.generate_totp_secret()
        encrypted = mfa.encrypt_secret(secret)
        assert encrypted != secret
        assert mfa.decrypt_secret(encrypted) == secret

    def test_encrypted_value_is_not_the_plaintext_substring(self):
        secret = mfa.generate_totp_secret()
        encrypted = mfa.encrypt_secret(secret)
        assert secret not in encrypted

    def test_decrypt_with_wrong_key_fails(self, monkeypatch):
        from cryptography.fernet import Fernet

        secret = mfa.generate_totp_secret()
        encrypted = mfa.encrypt_secret(secret)
        monkeypatch.setattr(mfa.settings, "mfa_encryption_key", Fernet.generate_key().decode())
        with pytest.raises(RuntimeError):
            mfa.decrypt_secret(encrypted)

    def test_missing_key_raises_clear_error(self, monkeypatch):
        monkeypatch.setattr(mfa.settings, "mfa_encryption_key", "")
        with pytest.raises(RuntimeError, match="MFA_ENCRYPTION_KEY"):
            mfa.encrypt_secret("JBSWY3DPEHPK3PXP")


class TestProvisioningUri:
    def test_contains_issuer_and_account(self):
        secret = mfa.generate_totp_secret()
        uri = mfa.provisioning_uri(secret, "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "user%40example.com" in uri or "user@example.com" in uri
        assert "CoreFusion" in uri


class TestVerifyTotpCode:
    def test_valid_current_code_verifies(self):
        secret = mfa.generate_totp_secret()
        code = pyotp.totp.TOTP(secret).now()
        assert mfa.verify_totp_code(secret, code) is True

    def test_wrong_code_rejected(self):
        secret = mfa.generate_totp_secret()
        real_code = pyotp.totp.TOTP(secret).now()
        wrong_code = "000000" if real_code != "000000" else "111111"
        assert mfa.verify_totp_code(secret, wrong_code) is False

    def test_non_numeric_code_rejected(self):
        secret = mfa.generate_totp_secret()
        assert mfa.verify_totp_code(secret, "abcdef") is False

    def test_empty_code_rejected(self):
        secret = mfa.generate_totp_secret()
        assert mfa.verify_totp_code(secret, "") is False

    def test_code_from_a_different_secret_is_rejected(self):
        secret_a = mfa.generate_totp_secret()
        secret_b = mfa.generate_totp_secret()
        code_for_b = pyotp.totp.TOTP(secret_b).now()
        # Extremely unlikely to collide, but guard against the flaky 1-in-a-million case.
        if pyotp.totp.TOTP(secret_a).now() == code_for_b:
            pytest.skip("codes coincidentally matched")
        assert mfa.verify_totp_code(secret_a, code_for_b) is False

    def test_previous_time_step_within_window_still_verifies(self):
        secret = mfa.generate_totp_secret()
        totp = pyotp.totp.TOTP(secret)
        previous_step_code = totp.at(int(time.time()) - 30)
        assert mfa.verify_totp_code(secret, previous_step_code) is True
