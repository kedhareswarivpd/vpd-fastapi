import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit import log_audit
from app.core.config import settings
from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.csrf import CSRFMiddleware
from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_client_ip
from app.core.errors import ApiError
from app.core.limiter import limiter
from app.core.logger import logger
from app.core.upstash_redis import get_upstash_redis_client
from app.core.sitemap import SITEMAP_ROUTES
from app.routers import api_router
from app.services.auth_service import get_session_by_access_token

_is_production = settings.env.lower() in {"production", "prod"}


def normalize_allowed_origins(origins: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    """Trim whitespace, remove trailing slashes, and de-duplicate origins.

    Render/Vercel often provide the same origin as both a full canonical URL and
    a copy with a trailing slash; the browser compares the exact Origin string,
    so we canonicalize to the bare origin before registering CORS.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in origins or []:
        origin = (value or "").strip()
        if not origin:
            continue
        origin = origin.rstrip("/")
        if not origin or origin in seen:
            continue
        cleaned.append(origin)
        seen.add(origin)
    return cleaned


app = FastAPI(
    title=settings.app_name,
    description="CoreFusion Technologies — Website, Admin Panel, Client Portal & Employee Portal API",
    version="1.0.0",
    # Swagger/Redoc leak the full route/schema surface; keep them out of production.
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Middleware is applied in reverse-registration order by Starlette:
# AuditMiddleware → CSRFMiddleware → SecurityHeadersMiddleware → CORSMiddleware (outermost last)
# CORS must be outermost so preflight OPTIONS responses are handled before any
# other middleware inspects the request.

_ALLOWED_ORIGINS = normalize_allowed_origins([
    settings.client_url,
    settings.site_url,
    *[o.strip() for o in settings.extra_cors_origins.split(",") if o.strip()],
])
if settings.env.lower() in {"development", "test", "local"}:
    _ALLOWED_ORIGINS.extend(normalize_allowed_origins(["http://localhost:5173", "http://localhost:4173"]))
_ALLOWED_ORIGINS = normalize_allowed_origins(_ALLOWED_ORIGINS)


# ---------- Security headers middleware ----------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)


# ---------- Audit middleware ----------
SKIP_AUDIT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/uploads"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in SKIP_AUDIT_PATHS):
            return await call_next(request)

        response = await call_next(request)

        if response.status_code < 200 or response.status_code >= 300:
            return response

        try:
            user_id = None
            token = request.cookies.get(ACCESS_TOKEN_COOKIE)
            if token:
                try:
                    # A dedicated short-lived session here rather than reusing
                    # any request-scoped one — this middleware runs outside
                    # the route handler's own `Depends(get_db)` lifecycle,
                    # after the handler's session has already been closed.
                    async with AsyncSessionLocal() as audit_db:
                        session = await get_session_by_access_token(audit_db, token)
                        if session is not None:
                            user_id = session.user_id
                except Exception:
                    pass

            entity_type = path.strip("/").split("/")[-2] if path.count("/") >= 2 else None
            entity_id = path.strip("/").split("/")[-1] if path.count("/") >= 2 else None
            try:
                entity_id = uuid.UUID(entity_id) if entity_id else None
            except (ValueError, TypeError):
                entity_id = None

            await log_audit(
                user_id=user_id,
                action=f"{request.method}_{path.strip('/').replace('/', '_')}",
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                log_metadata={"path": path, "query": str(request.query_params)},
            )
        except Exception as exc:
            logger.warning("Audit log failed: %s", exc)

        return response


app.add_middleware(AuditMiddleware)


# ---------- Request ID + structured access log middleware ----------
# CF-AUD-010: `X-Request-Id` was already declared in CORS's expose_headers
# but nothing ever generated or set it. This middleware generates (or
# forwards a caller-supplied) request ID, attaches it to the response, and
# emits one structured access-log line per request with the fields needed to
# diagnose latency/errors in production (method, path, status, duration,
# request id) — without adding a new logging dependency.
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        # Defensive default for a real bug found via a live Redis-outage drill
        # (see status.md): slowapi 0.1.9's rate-limit decorator only sets
        # `request.state.view_rate_limit` *after* its limit check succeeds —
        # if the check raises (e.g. Redis unreachable) and `swallow_errors=True`
        # swallows that, the decorator still unconditionally reads this
        # attribute afterward to inject response headers, crashing every
        # request with AttributeError for as long as Redis stays down. A sane
        # default here means "no limit info to report" instead of a crash.
        request.state.view_rate_limit = None
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request_id=%s method=%s path=%s status=500 duration_ms=%.1f",
                request_id, request.method, request.url.path, duration_ms,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id
        log_level = logger.warning if response.status_code >= 500 else logger.info
        log_level(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        return response


app.add_middleware(RequestContextMiddleware)

# CORSMiddleware is registered last so Starlette places it outermost —
# it runs first on every request, including OPTIONS preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-CSRF-Token"],
    expose_headers=["X-Request-Id"],
    max_age=600,
)


# ---------- Static file serving for uploaded assets ----------
upload_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.upload_dir)
os.makedirs(upload_root, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_root), name="uploads")


# ---------- Error handling ----------
@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    if exc.status_code >= 500:
        logger.error("%s %s - %s", request.method, request.url.path, exc.message)
    else:
        logger.warning("%s %s - %s", request.method, request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "status_code": exc.status_code, "message": exc.message, "errors": exc.errors},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    errors = []
    message = "Request failed"

    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("msg") or message
        errors = detail.get("errors") or []
    elif isinstance(detail, list):
        errors = detail
        if detail and isinstance(detail[0], dict):
            message = detail[0].get("msg") or message
    elif detail:
        message = str(detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "status_code": exc.status_code, "message": message, "errors": errors},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"success": False, "status_code": 422, "message": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "status_code": 500, "message": "Internal Server Error"},
    )


# ---------- Health check ----------
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    """Liveness only — does not touch the database. A load balancer/orchestrator
    should use this to decide whether to restart the process."""
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness — verifies the database and Upstash REST Redis are both
    reachable before traffic is routed here."""
    from sqlalchemy import text

    from app.core.database import AsyncSessionLocal

    checks = {}
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — DB failure means not-ready.
        checks["database"] = f"unreachable: {exc}"

    redis_client = get_upstash_redis_client()
    if redis_client is None:
        checks["redis"] = "unreachable: Upstash REST client not configured"
    else:
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001 — Redis is required for readiness.
            logger.warning("Redis health check failed: %s", exc)
            checks["redis"] = f"unreachable: {exc}"

    all_ok = checks.get("database") == "ok" and checks.get("redis") == "ok"
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )


@app.get("/sitemap.xml", tags=["SEO"])
async def sitemap():
    from fastapi.responses import Response

    base_url = settings.site_url
    urls = "\n".join(
        f'  <url><loc>{base_url}{r["path"]}</loc><priority>{r["priority"]}</priority></url>'
        for r in SITEMAP_ROUTES
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>"""
    return Response(content=xml.strip(), media_type="application/xml")


# ---------- API routes ----------
app.include_router(api_router, prefix=settings.api_prefix)
