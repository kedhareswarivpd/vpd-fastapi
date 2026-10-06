"""Unit tests for the opaque session/reset/verification token primitives
(app/core/tokens.py) — the mechanism CoreFusion-owned sessions, password
resets, and email verification all build on."""
from app.core.tokens import generate_token, hash_token


class TestGenerateToken:
    def test_produces_a_non_empty_url_safe_string(self):
        token = generate_token()
        assert len(token) > 20
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_two_calls_produce_different_tokens(self):
        assert generate_token() != generate_token()


class TestHashToken:
    def test_same_input_hashes_identically(self):
        token = generate_token()
        assert hash_token(token) == hash_token(token)

    def test_different_inputs_hash_differently(self):
        assert hash_token("token-a") != hash_token("token-b")

    def test_hash_is_a_64_char_hex_digest(self):
        digest = hash_token("anything")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_hash_does_not_reveal_the_original_token(self):
        token = generate_token()
        assert hash_token(token) != token
