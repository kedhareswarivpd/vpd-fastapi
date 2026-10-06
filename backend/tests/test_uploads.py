"""Unit tests for file upload validation and security."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import ApiError
from app.utils.uploads import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME,
    ALLOWED_SUBFOLDERS,
    _verify_magic,
    load_private_file,
    save_upload,
)


class TestVerifyMagic:
    def test_valid_jpeg_magic_bytes(self):
        assert _verify_magic("image/jpeg", b"\xff\xd8\xff\xe0\x00\x10JFIF") is True

    def test_valid_png_magic_bytes(self):
        assert _verify_magic("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00") is True

    def test_valid_gif_magic_bytes(self):
        assert _verify_magic("image/gif", b"GIF89a\x01\x00\x01\x00") is True

    def test_valid_pdf_magic_bytes(self):
        assert _verify_magic("application/pdf", b"%PDF-1.4") is True

    def test_valid_zip_magic_bytes(self):
        assert _verify_magic("application/zip", b"PK\x03\x04\x00\x00") is True

    def test_valid_webp_magic_bytes(self):
        assert _verify_magic("image/webp", b"RIFF\x00\x00\x00\x00WEBP") is True

    def test_valid_mp4_magic_bytes(self):
        assert _verify_magic("video/mp4", b"\x00\x00\x00\x18ftypmp42") is True

    def test_invalid_magic_bytes_rejected(self):
        assert _verify_magic("image/jpeg", b"NOTAJPEGIMAGE") is False

    def test_text_plain_valid_utf8(self):
        assert _verify_magic("text/plain", b"Hello, World!") is True

    def test_text_plain_rejects_nul_bytes(self):
        assert _verify_magic("text/plain", b"Hello\x00World") is False

    def test_text_plain_rejects_non_utf8(self):
        assert _verify_magic("text/plain", b"\xff\xfe\x00\x01") is False

    def test_unknown_mime_rejected(self):
        assert _verify_magic("application/x-evil", b"anything") is False

    def test_valid_bmp_magic_bytes(self):
        assert _verify_magic("image/bmp", b"BM\x00\x00") is True

    def test_valid_gzip_magic_bytes(self):
        assert _verify_magic("application/gzip", b"\x1f\x8b\x08") is True

    def test_valid_7z_magic_bytes(self):
        assert _verify_magic("application/x-7z-compressed", b"7z\xbc\xaf\x27\x1c") is True


class TestSaveUpload:
    @pytest.mark.asyncio
    async def test_rejects_disallowed_mime_type(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/x-evil"
        mock_file.filename = "evil.exe"

        with pytest.raises(ApiError) as exc_info:
            await save_upload(mock_file, "media")
        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_rejects_disallowed_extension(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "text/plain"
        mock_file.filename = "malware.exe"

        with pytest.raises(ApiError) as exc_info:
            await save_upload(mock_file, "media")
        assert exc_info.value.status_code == 400
        assert "Unsupported file extension" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_rejects_disallowed_subfolder(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "photo.png"
        mock_file.read = MagicMock(return_value=b"\x89PNG\r\n\x1a\n")

        with pytest.raises(ApiError) as exc_info:
            await save_upload(mock_file, "etc")
        assert exc_info.value.status_code == 400
        assert "Unsupported upload folder" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_rejects_file_exceeding_size_limit(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "large.png"
        large_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)
        mock_file.read = AsyncMock(return_value=large_content)

        with patch.object(settings, "max_file_size_mb", 10):
            with pytest.raises(ApiError) as exc_info:
                await save_upload(mock_file, "media")
            assert exc_info.value.status_code == 400
            assert "exceeds" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_rejects_mismatched_magic_bytes(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "fake.png"
        mock_file.read = AsyncMock(return_value=b"NOTAPNGIMAGE")

        with pytest.raises(ApiError) as exc_info:
            await save_upload(mock_file, "media")
        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_accepts_valid_upload(self, tmp_path):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "photo.png"
        mock_file.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        with patch("app.utils.uploads.UPLOAD_ROOT", str(tmp_path)):
            result = await save_upload(mock_file, "media")

        assert result.startswith("/uploads/media/")
        assert result.endswith(".png")

    @pytest.mark.asyncio
    async def test_empty_subfolder_defaults_to_misc(self, tmp_path):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "photo.png"
        mock_file.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        with patch("app.utils.uploads.UPLOAD_ROOT", str(tmp_path)):
            result = await save_upload(mock_file, "")

        assert "/uploads/misc/" in result

    @pytest.mark.asyncio
    async def test_path_traversal_prevented(self, tmp_path):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "photo.png"
        mock_file.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        with patch("app.utils.uploads.UPLOAD_ROOT", str(tmp_path)):
            with pytest.raises(ApiError) as exc_info:
                await save_upload(mock_file, "../../../etc")
            assert exc_info.value.status_code == 400
            assert "Unsupported upload folder" in exc_info.value.message


class TestSaveUploadS3Backend:
    """Same validation logic, routed through storage_service instead of disk
    when STORAGE_BACKEND=s3 (MinIO locally, Supabase Storage in staging) —
    boto3 itself is exercised for real in test_storage_service.py; here only
    the branch inside save_upload/load_private_file is under test."""

    @pytest.mark.asyncio
    async def test_public_upload_calls_put_object_and_returns_public_url(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "image/png"
        mock_file.filename = "photo.png"
        mock_file.read = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        with patch.object(settings, "storage_backend", "s3"):
            with patch("app.utils.uploads.storage_service.put_object", new_callable=AsyncMock) as mock_put:
                with patch("app.utils.uploads.storage_service.public_url", return_value="http://minio:9000/bucket/public/media/x.png") as mock_url:
                    result = await save_upload(mock_file, "media")

        mock_put.assert_called_once()
        key_arg = mock_put.call_args.args[0]
        assert key_arg.startswith("public/media/")
        mock_url.assert_called_once_with(key_arg)
        assert result == "http://minio:9000/bucket/public/media/x.png"

    @pytest.mark.asyncio
    async def test_private_upload_returns_bare_reference_not_a_url(self):
        mock_file = MagicMock(spec=UploadFile)
        mock_file.content_type = "application/pdf"
        mock_file.filename = "resume.pdf"
        mock_file.read = AsyncMock(return_value=b"%PDF-1.4")

        with patch.object(settings, "storage_backend", "s3"):
            with patch("app.utils.uploads.storage_service.put_object", new_callable=AsyncMock) as mock_put:
                result = await save_upload(mock_file, "careers")

        key_arg = mock_put.call_args.args[0]
        assert key_arg.startswith("private/careers/")
        assert result == f"careers/{key_arg.split('/')[-1]}"
        assert not result.startswith("http")
        assert not result.startswith("/uploads")


class TestLoadPrivateFileS3Backend:
    @pytest.mark.asyncio
    async def test_fetches_object_with_private_prefix(self):
        with patch.object(settings, "storage_backend", "s3"):
            with patch("app.utils.uploads.storage_service.get_object", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = b"%PDF-1.4 fake resume"
                content, filename, content_type = await load_private_file("careers/12345-abcdef.pdf", "careers")

        mock_get.assert_called_once_with("private/careers/12345-abcdef.pdf")
        assert content == b"%PDF-1.4 fake resume"
        assert filename == "12345-abcdef.pdf"
        assert content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_missing_object_raises_not_found(self):
        with patch.object(settings, "storage_backend", "s3"):
            with patch("app.utils.uploads.storage_service.get_object", new_callable=AsyncMock, side_effect=FileNotFoundError):
                with pytest.raises(ApiError) as exc_info:
                    await load_private_file("careers/missing.pdf", "careers")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_rejected_before_any_s3_call(self):
        with patch.object(settings, "storage_backend", "s3"):
            with patch("app.utils.uploads.storage_service.get_object", new_callable=AsyncMock) as mock_get:
                with pytest.raises(ApiError) as exc_info:
                    await load_private_file("../../etc/passwd", "careers")
        assert exc_info.value.status_code == 400
        mock_get.assert_not_called()


class TestAllowedConstants:
    def test_svg_not_in_allowed_mime(self):
        assert "image/svg+xml" not in ALLOWED_MIME

    def test_svg_extension_not_allowed(self):
        assert ".svg" not in ALLOWED_EXTENSIONS

    def test_executable_extension_not_allowed(self):
        assert ".exe" not in ALLOWED_EXTENSIONS

    def test_php_extension_not_allowed(self):
        assert ".php" not in ALLOWED_EXTENSIONS

    def test_subfolders_allowlist_exists(self):
        assert "media" in ALLOWED_SUBFOLDERS
        assert "projects" in ALLOWED_SUBFOLDERS
        assert "etc" not in ALLOWED_SUBFOLDERS
