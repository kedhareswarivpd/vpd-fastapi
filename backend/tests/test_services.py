"""Unit tests for email and notification services.

(Supabase-client tests — TestGetAnonClient/TestGetAdminClient/
TestCreateOrFindSupabaseUser — were removed along with
app/services/supabase_client.py in the Supabase Auth -> CoreFusion Auth
migration; equivalent coverage for the new auth mechanism lives in
tests/test_auth_service.py, tests/test_password.py, and tests/test_tokens.py.)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.services.email_service import (
    _esc,
    send_contact_notification,
    send_email,
    send_password_reset_email,
    send_welcome_email,
)
from app.services.notification_service import notify_roles, notify_user


class TestSendEmail:
    @pytest.mark.asyncio
    async def test_skips_when_no_brevo_api_key_configured(self):
        with patch.object(settings, "brevo_api_key", ""):
            with patch("app.services.email_service.httpx.AsyncClient") as mock_client_cls:
                await send_email("test@example.com", "Subject", "<p>Body</p>")
                mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_posts_to_brevo_api_when_configured(self):
        mock_response = MagicMock(status_code=201)
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client

        with patch.object(settings, "brevo_api_key", "xkeysib-test-key"):
            with patch.object(settings, "brevo_sender_email", "noreply@example.com"):
                with patch("app.services.email_service.httpx.AsyncClient", return_value=mock_client):
                    await send_email("to@example.com", "Subject", "<p>Body</p>")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://api.brevo.com/v3/smtp/email"
        assert call_args.kwargs["headers"]["api-key"] == "xkeysib-test-key"
        assert call_args.kwargs["json"]["to"] == [{"email": "to@example.com"}]
        assert call_args.kwargs["json"]["sender"]["email"] == "noreply@example.com"
        assert call_args.kwargs["json"]["htmlContent"] == "<p>Body</p>"

    @pytest.mark.asyncio
    async def test_logs_error_on_brevo_rejection_without_raising(self):
        mock_response = MagicMock(status_code=401, text="Unauthorized")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client

        with patch.object(settings, "brevo_api_key", "invalid-key"):
            with patch("app.services.email_service.httpx.AsyncClient", return_value=mock_client):
                with patch("app.services.email_service.logger") as mock_logger:
                    await send_email("to@example.com", "Subject", "<p>Body</p>")  # must not raise
                    mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_error_on_network_failure(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection refused")
        mock_client.__aenter__.return_value = mock_client

        with patch.object(settings, "brevo_api_key", "xkeysib-test-key"):
            with patch("app.services.email_service.httpx.AsyncClient", return_value=mock_client):
                with patch("app.services.email_service.logger") as mock_logger:
                    await send_email("to@example.com", "Subject", "<p>Body</p>")
                    mock_logger.error.assert_called_once()


class TestEsc:
    def test_escapes_html_entities(self):
        assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

    def test_escapes_ampersand(self):
        assert _esc("A & B") == "A &amp; B"

    def test_handles_none(self):
        assert _esc(None) == ""

    def test_handles_numbers(self):
        assert _esc(42) == "42"


class TestSendWelcomeEmail:
    @pytest.mark.asyncio
    async def test_sends_welcome_with_escaped_name(self):
        with patch("app.services.email_service.send_email") as mock_send:
            await send_welcome_email("John <script>", "john@example.com")
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "john@example.com"
            assert "Welcome" in call_args[0][1]
            assert "&lt;script&gt;" in call_args[0][2]


class TestSendPasswordResetEmail:
    @pytest.mark.asyncio
    async def test_sends_reset_with_safe_url(self):
        with patch("app.services.email_service.send_email") as mock_send:
            await send_password_reset_email(
                "John", "john@example.com", "https://example.com/reset?token=abc"
            )
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Password Reset" in call_args[0][1]
            assert "https://example.com/reset?token=abc" in call_args[0][2]


class TestSendContactNotification:
    @pytest.mark.asyncio
    async def test_sends_to_brevo_sender_email(self):
        with patch.object(settings, "brevo_sender_email", "admin@example.com"):
            with patch("app.services.email_service.send_email") as mock_send:
                await send_contact_notification(
                    "Jane", "jane@example.com", "Hello!", "Support"
                )
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args[0][0] == "admin@example.com"
                assert "Jane" in call_args[0][2]
                assert "jane@example.com" in call_args[0][2]


class TestNotifyUser:
    @pytest.mark.asyncio
    async def test_creates_notification(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        user_id = uuid.uuid4()

        await notify_user(mock_db, user_id, "Test Title", "Test Message")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

        notification = mock_db.add.call_args[0][0]
        assert isinstance(notification, Notification)
        assert notification.user_id == user_id
        assert notification.title == "Test Title"
        assert notification.message == "Test Message"
        assert notification.type == NotificationType.info

    @pytest.mark.asyncio
    async def test_creates_notification_with_link(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        user_id = uuid.uuid4()

        await notify_user(
            mock_db, user_id, "Alert", "Check this", NotificationType.warning, "/dashboard"
        )

        notification = mock_db.add.call_args[0][0]
        assert notification.link == "/dashboard"
        assert notification.type == NotificationType.warning


class TestNotifyRoles:
    @pytest.mark.asyncio
    async def test_fans_out_to_matching_users(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        user_ids = [uuid.uuid4(), uuid.uuid4()]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = user_ids
        mock_db.execute.return_value = mock_result

        await notify_roles(mock_db, ["admin", "hr"], "New Policy", "Please review")

        assert mock_db.add.call_count == 2
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_commit_when_no_matching_users(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await notify_roles(mock_db, ["nonexistent"], "Title", "Message")

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

