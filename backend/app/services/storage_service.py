"""S3-compatible object storage — MinIO locally, Supabase Storage's
S3-compatible API in staging/production. Both speak the same S3 API, so this
one module serves both; only `settings.s3_endpoint_url` /
`s3_access_key_id` / `s3_secret_access_key` / `s3_bucket` differ per
environment (see core/config.py).

boto3 is synchronous — every call here runs on a worker thread via
`asyncio.to_thread` so it never blocks the event loop, the same concern that
justifies the async ORM/driver choices elsewhere in this app.
"""
import asyncio
import json
import threading

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logger import logger


# Grants anonymous GetObject only under the "public/" prefix — mirrors the
# local-disk backend's separation of UPLOAD_ROOT (servable) from
# PRIVATE_UPLOAD_ROOT (never servable): private/* objects stay unreadable
# without going through this app's own authenticated download endpoint,
# exactly like on disk. Only applied for auto-created buckets (MinIO) — a
# provider like Supabase Storage manages its own bucket's public/private
# setting via its own dashboard, and s3_auto_create_bucket=false there means
# this app never touches that bucket's policy.
def _public_read_policy(bucket: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket}/public/*"],
        }],
    })

_client = None
_client_lock = threading.Lock()
_bucket_ensured = False


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = boto3.client(
                    "s3",
                    endpoint_url=settings.s3_endpoint_url or None,
                    aws_access_key_id=settings.s3_access_key_id or None,
                    aws_secret_access_key=settings.s3_secret_access_key or None,
                    region_name=settings.s3_region or "us-east-1",
                    config=BotoConfig(
                        s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
                    ),
                )
    return _client


def _ensure_bucket_sync() -> None:
    global _bucket_ensured
    if _bucket_ensured or not settings.s3_auto_create_bucket:
        return
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
            logger.info("Created S3 bucket %s", settings.s3_bucket)
        except ClientError as exc:
            # A managed provider (e.g. Supabase Storage) may not support or
            # need bucket auto-creation — the bucket is expected to already
            # exist there. Logged, not raised: the actual put/get call below
            # will surface a real error if the bucket genuinely doesn't exist.
            logger.info("Could not auto-create S3 bucket %s (%s) — assuming it already exists", settings.s3_bucket, exc)
            _bucket_ensured = True
            return

    # A freshly created (or freshly confirmed-existing, e.g. after a MinIO
    # container restart with a persisted volume) auto-managed bucket
    # defaults to fully private — found via a live upload+fetch drill that
    # returned 403 on a public/* object despite the upload itself succeeding.
    # Applied idempotently every time this ensure runs, not just on first
    # creation, since PutBucketPolicy is cheap and a persisted MinIO volume
    # can otherwise carry a bucket that exists but was never given this
    # policy in an earlier version of this code.
    try:
        client.put_bucket_policy(Bucket=settings.s3_bucket, Policy=_public_read_policy(settings.s3_bucket))
    except ClientError as exc:
        logger.warning("Could not set public-read policy on S3 bucket %s (%s)", settings.s3_bucket, exc)
    _bucket_ensured = True


async def put_object(key: str, data: bytes, content_type: str) -> None:
    def _put():
        _ensure_bucket_sync()
        _get_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)

    await asyncio.to_thread(_put)


async def get_object(key: str) -> bytes:
    def _get():
        response = _get_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()

    try:
        return await asyncio.to_thread(_get)
    except ClientError as exc:
        raise FileNotFoundError(key) from exc


def public_url(key: str) -> str:
    base = (settings.s3_public_url_base or settings.s3_endpoint_url).rstrip("/")
    return f"{base}/{key}"
