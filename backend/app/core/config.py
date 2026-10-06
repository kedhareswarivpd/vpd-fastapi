import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Which .env file to load — defaults to backend/.env (local dev), but
# scripts/migrate.sh (and anything else targeting a different environment,
# e.g. staging) can set ENV_FILE=.env.staging in the process environment
# before starting Python. Deliberately NOT done by having callers `source`
# the .env file in bash first — .env syntax isn't bash syntax (e.g.
# SMTP_FROM's `Name <email>` format breaks bash's `<` as redirection) and
# that produced real, confusing failures when tried. Let pydantic-settings'
# real dotenv parser handle it instead.
_ENV_FILE = os.environ.get("ENV_FILE") or str(BACKEND_ROOT / ".env")

# SQLAlchemy driver aliases used to switch a `postgresql://` URL between the
# async and sync dialects. The order matters for prefixes like
# `postgresql+asyncpg://` which already contain a `+`.
_DRIVER_ALIASES = (
    ("postgresql+asyncpg://", "postgresql+psycopg2://"),
    ("postgresql+psycopg2://", "postgresql+asyncpg://"),
    ("postgresql://", "postgresql+asyncpg://"),
    ("postgresql://", "postgresql+psycopg2://"),
)


def _as_scheme(url: str, scheme: str) -> str:
    """Convert a PostgreSQL URL to the given driver scheme, leaving others untouched."""
    for old, new in _DRIVER_ALIASES:
        if new == scheme and url.startswith(old):
            return scheme + url[len(old):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    env: str = "development"
    app_name: str = "VPD Technologies"
    api_prefix: str = "/api/v1"
    client_url: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CLIENT_URL", "FRONTEND_URL"),
    )
    port: int = 8000

    # Database - can be set via DATABASE_URL or individual components
    database_url: str = ""  # Full PostgreSQL URL (takes precedence)
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_pass: str = ""
    db_use_pgbouncer: bool = False  # set True when pointing at Supabase's transaction pooler (port 6543)
    # Sized so 4 gunicorn workers (docker/Dockerfile) x (pool_size+max_overflow)
    # stays safely under a vanilla Postgres' default max_connections=100 with
    # headroom for migrations/admin/other consumers: 4 x 20 = 80. When
    # DB_USE_PGBOUNCER=true, PgBouncer's transaction-mode multiplexing means
    # these can be raised well above what direct-to-Postgres would allow —
    # see backend/performance/pool_matrix_test.py for the measurements this
    # sizing is based on (CF-BE-009).
    db_pool_size: int = 10
    db_max_overflow: int = 10

    # Redis — a local container in dev, Upstash (managed, TLS-required Redis)
    # in staging. Prefer the full REDIS_URL value from the environment, e.g.
    # `rediss://default:<token>@<host>:<port>` — that is what Upstash exposes
    # in its "Connect" tab and it is the only form the app should use in
    # deployed environments. The older host/port/password fallback remains only
    # for local container development and should not be used for Upstash.
    redis_url_override: str = Field(
        default="",
        validation_alias=AliasChoices("REDIS_URL_OVERRIDE", "REDIS_URL"),
    )
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_tls: bool = False  # forces rediss:// when building from host/port/password instead of redis_url_override

    # Email — Brevo's transactional email HTTP API (not SMTP; see
    # services/email_service.py). One account/API key serves every
    # environment (local dev and staging both send through Brevo per
    # explicit instruction) — there is no separate "local" email path.
    brevo_api_key: str = ""
    brevo_sender_email: str = "no-reply@corefusiontech.com"
    brevo_sender_name: str = "VPD Technologies"

    # Uploads / file storage. "local" (default) writes to local disk exactly
    # as before — nothing changes for a deployment that doesn't set these.
    # "s3" routes every upload through an S3-compatible bucket instead
    # (core/storage_service.py) — MinIO locally, Supabase Storage's
    # S3-compatible API in staging/production; the same code path serves
    # both since both speak the S3 API, only the endpoint/credentials differ
    # per environment.
    storage_backend: str = "local"  # "local" | "s3"
    upload_dir: str = "uploads"
    max_file_size_mb: int = 10

    s3_endpoint_url: str = ""  # e.g. http://minio:9000 (local) or https://<project-ref>.supabase.co/storage/v1/s3 (staging)
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = "vpdtechnologies-uploads"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True  # required by MinIO; harmless elsewhere
    s3_public_url_base: str = ""  # e.g. http://localhost:9000/corefusion-uploads (local) or https://<project-ref>.supabase.co/storage/v1/object/public/corefusion-uploads (staging)
    s3_auto_create_bucket: bool = True  # convenient for MinIO's empty local volume; a no-op (caught, ignored) if the bucket already exists, e.g. on Supabase

    # Site
    site_url: str = "https://www.vpdtechnologies.com"

    # Rate limiting
    rate_limit: str = "300/15minute"

    # Extra CORS origins (comma-separated, e.g. for Vercel preview URLs)
    extra_cors_origins: str = Field(
        default="",
        validation_alias=AliasChoices("EXTRA_CORS_ORIGINS", "CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )

    # Trust `x-forwarded-for` for client IP (only when behind a known proxy/load balancer)
    trust_proxy_headers: bool = False

    # MFA / 2FA (TOTP) — OFF by default for every account. This is a global
    # kill switch: when False, every /auth/mfa/* endpoint responds 404 (the
    # feature doesn't exist as far as any caller can tell) regardless of any
    # per-user state, and login never branches into the MFA-challenge path.
    # Flipping this to True does NOT turn MFA on for existing users — each
    # account still opts in individually via POST /auth/mfa/setup +
    # POST /auth/mfa/enable. mfa_encryption_key must be a valid Fernet key
    # (generate with `python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"`) before mfa_enabled=True is used
    # for real — app/core/mfa.py raises clearly at call time if it's missing.
    mfa_enabled: bool = False
    mfa_issuer: str = "CoreFusion Technologies"
    mfa_encryption_key: str = ""

    # OAuth / social login — OFF by default. oauth_enabled is the same kind
    # of global kill switch as mfa_enabled: when False, every /auth/oauth/*
    # endpoint responds 404. Each provider is additionally only usable once
    # its own client_id/client_secret/redirect_uri are all set — an unset
    # provider's login/callback routes 404 individually even if oauth_enabled
    # is True, so partial configuration (e.g. Google only) is safe.
    oauth_enabled: bool = False
    oauth_success_redirect_url: str = ""  # defaults to client_url if unset
    oauth_failure_redirect_url: str = ""  # defaults to client_url if unset

    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_google_redirect_uri: str = ""

    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_github_redirect_uri: str = ""

    def _get_async_database_url(self) -> str:
        """Get the async PostgreSQL URL."""
        return _as_scheme(self.database_url, "postgresql+asyncpg://") if self.database_url else (
            f"postgresql+asyncpg://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def _get_sync_database_url(self) -> str:
        """Get the sync PostgreSQL URL (for Alembic migrations)."""
        return _as_scheme(self.database_url, "postgresql+psycopg2://") if self.database_url else (
            f"postgresql+psycopg2://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_database_url(self) -> str:
        """Get the async database URL."""
        return self._get_async_database_url()

    @property
    def sync_database_url(self) -> str:
        """Get the sync database URL (used by Alembic for migrations)."""
        return self._get_sync_database_url()

    @property
    def redis_url(self) -> str:
        # socket_connect_timeout/socket_timeout: without these, redis-py's
        # default connect/read timeouts are long enough that every request
        # blocks for several seconds when Redis is unreachable, rather than
        # failing fast into `swallow_errors=True`'s fallback path — found via
        # a live Redis-outage drill (killed Redis mid-traffic and measured
        # ~4-8s per request, severe enough to trigger a gunicorn worker
        # SIGABRT from request pile-up). The actual amplification factor
        # observed end-to-end in the real gunicorn app (multiple rate-limit
        # checks/retries per request) was higher than isolated single-call
        # testing suggested — 0.3s alone still produced multi-second request
        # latency in the full app. 0.05s keeps even a large amplification
        # factor well under 1s, while still being generous for a healthy
        # same-network Redis (sub-ms normally). Also applied to
        # redis_url_override (e.g. Upstash) — a managed Redis being briefly
        # unreachable is exactly the scenario CF-BE-014 was found under, and
        # nothing about that failure mode is specific to a local container.
        timeout_params = "socket_connect_timeout=0.05&socket_timeout=0.05"
        if self.redis_url_override:
            normalized = self.redis_url_override.strip()
            if normalized.startswith("redis://") and not normalized.startswith("rediss://"):
                normalized = "rediss://" + normalized[len("redis://"):]
            separator = "&" if "?" in normalized else "?"
            return f"{normalized}{separator}{timeout_params}"
        scheme = "rediss" if self.redis_tls else "redis"
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"{scheme}://{auth}{self.redis_host}:{self.redis_port}?{timeout_params}"

    @property
    def redis_diagnostics(self) -> dict[str, bool]:
        configured = bool((self.redis_url_override or "").strip())
        effective_url = (self.redis_url or "").strip()
        tls = effective_url.startswith("rediss://")
        upstash = bool(effective_url and "upstash.io" in effective_url.lower())
        return {
            "configured": configured,
            "tls": tls,
            "using_upstash": upstash,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
