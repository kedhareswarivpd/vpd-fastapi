"""Unit tests for app/services/storage_service.py — the S3-compatible object
storage layer shared by MinIO (local) and Supabase Storage (staging). boto3
is mocked throughout; a real round trip against a live MinIO container is
verified separately by hand (see status.md), not by this automated suite.
"""
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services import storage_service


@pytest.fixture(autouse=True)
def _reset_client_cache():
    storage_service._client = None
    storage_service._bucket_ensured = False
    yield
    storage_service._client = None
    storage_service._bucket_ensured = False


@pytest.fixture(autouse=True)
def _s3_settings(monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://minio:9000")
    monkeypatch.setattr(settings, "s3_access_key_id", "test-key")
    monkeypatch.setattr(settings, "s3_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    monkeypatch.setattr(settings, "s3_public_url_base", "http://localhost:9000/test-bucket")
    monkeypatch.setattr(settings, "s3_auto_create_bucket", True)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "HeadBucket")


class TestPutObject:
    @pytest.mark.asyncio
    async def test_calls_put_object_with_correct_args(self):
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.return_value = {}  # bucket already exists

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("public/media/photo.png", b"binarydata", "image/png")

        mock_boto_client.put_object.assert_called_once_with(
            Bucket="test-bucket", Key="public/media/photo.png", Body=b"binarydata", ContentType="image/png",
        )

    @pytest.mark.asyncio
    async def test_auto_creates_missing_bucket(self):
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.side_effect = _client_error("404")

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("public/media/photo.png", b"data", "image/png")

        mock_boto_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    async def test_bucket_creation_failure_does_not_raise(self):
        """A managed provider (Supabase Storage) may reject bucket creation
        outright — the bucket is expected to already exist there. This must
        be swallowed, not propagated, so the actual put_object call still
        gets a chance to succeed or fail on its own merits."""
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.side_effect = _client_error("404")
        mock_boto_client.create_bucket.side_effect = _client_error("AccessDenied")

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("public/media/photo.png", b"data", "image/png")  # must not raise

        mock_boto_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_newly_created_bucket_gets_a_public_read_policy_scoped_to_public_prefix(self):
        """Regression test for a real bug found via a live upload+fetch
        drill: a freshly auto-created MinIO bucket defaults to fully
        private, so an uploaded public/* object 403'd on GET despite the
        upload itself succeeding. The policy must be applied, and must only
        grant access under 'public/*' — private/* (career resumes etc.)
        must stay unreadable even via a guessed direct URL."""
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.side_effect = _client_error("404")

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("public/media/photo.png", b"data", "image/png")

        mock_boto_client.put_bucket_policy.assert_called_once()
        call_kwargs = mock_boto_client.put_bucket_policy.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        policy = call_kwargs["Policy"]
        assert "test-bucket/public/*" in policy
        assert "test-bucket/private/*" not in policy
        assert '"Effect": "Allow"' in policy

    @pytest.mark.asyncio
    async def test_policy_application_failure_does_not_raise(self):
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.side_effect = _client_error("404")
        mock_boto_client.put_bucket_policy.side_effect = _client_error("AccessDenied")

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("public/media/photo.png", b"data", "image/png")  # must not raise

        mock_boto_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_bucket_ensure_only_runs_once_per_process(self):
        mock_boto_client = MagicMock()
        mock_boto_client.head_bucket.return_value = {}

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            await storage_service.put_object("a", b"1", "text/plain")
            await storage_service.put_object("b", b"2", "text/plain")

        assert mock_boto_client.head_bucket.call_count == 1


class TestGetObject:
    @pytest.mark.asyncio
    async def test_returns_object_body_bytes(self):
        mock_body = MagicMock()
        mock_body.read.return_value = b"file-contents"
        mock_boto_client = MagicMock()
        mock_boto_client.get_object.return_value = {"Body": mock_body}

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            result = await storage_service.get_object("private/careers/resume.pdf")

        assert result == b"file-contents"
        mock_boto_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="private/careers/resume.pdf")

    @pytest.mark.asyncio
    async def test_missing_object_raises_file_not_found(self):
        mock_boto_client = MagicMock()
        mock_boto_client.get_object.side_effect = _client_error("NoSuchKey")

        with patch("app.services.storage_service.boto3.client", return_value=mock_boto_client):
            with pytest.raises(FileNotFoundError):
                await storage_service.get_object("private/careers/missing.pdf")


class TestPublicUrl:
    def test_uses_public_url_base_when_set(self):
        assert storage_service.public_url("public/media/photo.png") == "http://localhost:9000/test-bucket/public/media/photo.png"

    def test_falls_back_to_endpoint_url_when_public_base_unset(self, monkeypatch):
        monkeypatch.setattr(settings, "s3_public_url_base", "")
        assert storage_service.public_url("public/media/photo.png") == "http://minio:9000/public/media/photo.png"
