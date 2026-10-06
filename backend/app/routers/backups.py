import asyncio
import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.config import BACKEND_ROOT, settings
from app.core.dependencies import require_roles
from app.core.errors import ApiError
from app.core.logger import logger
from app.utils.responses import success_response

# Real pg_dump-backed backups (not a fabricated/mocked listing) — production
# use should still layer on managed provider backups (Supabase's own
# point-in-time recovery, etc.); this gives the Admin Panel's "Backups" module
# (PDF section 5) a genuine, working manual-backup surface: trigger a dump,
# list what actually exists on disk, download it, delete it.
router = APIRouter(prefix="/backups", tags=["Backups"], dependencies=[Depends(require_roles("super_admin"))])

BACKUP_DIR = BACKEND_ROOT / "backups"
_FILENAME_RE = re.compile(r"^corefusion-[a-z]+-\d{8}T\d{6}Z\.dump$")


def _pg_dump_args() -> tuple[list[str], dict[str, str]]:
    """Builds the pg_dump argv + env (PGPASSWORD) from the app's own DB
    settings, so this works against either the local Postgres container or a
    Supabase-hosted database without separate configuration."""
    import os

    if settings.database_url:
        parsed = urlparse(settings.database_url.replace("+asyncpg", "").replace("+psycopg2", ""))
        host, port = parsed.hostname, parsed.port or 5432
        user, password, dbname = parsed.username, parsed.password or "", (parsed.path or "/").lstrip("/")
    else:
        host, port = settings.db_host, settings.db_port
        user, password, dbname = settings.db_user, settings.db_pass, settings.db_name

    args = ["pg_dump", "-h", host, "-p", str(port), "-U", user, "-d", dbname, "-Fc", "--no-owner", "--no-privileges"]
    env = {**os.environ, "PGPASSWORD": password}
    return args, env


@router.get("", response_model=dict)
async def list_backups():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("vpdtechnologies-*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    data = [
        {
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=UTC).isoformat(),
        }
        for f in files
    ]
    return success_response(data=data, message="Backups fetched")


@router.post("/trigger", response_model=dict, status_code=201)
async def trigger_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"vpdtechnologies-{settings.env.lower()}-{timestamp}.dump"
    dest = BACKUP_DIR / filename

    args, env = _pg_dump_args()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, "-f", str(dest), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    except FileNotFoundError as exc:
        raise ApiError.internal("pg_dump is not available in this environment") from exc
    except TimeoutError as exc:
        raise ApiError.internal("Backup timed out after 5 minutes") from exc

    if proc.returncode != 0:
        dest.unlink(missing_ok=True)
        logger.error("pg_dump failed (exit %s): %s", proc.returncode, stderr.decode(errors="replace")[:2000])
        raise ApiError.internal("Backup failed — see server logs for details")

    return success_response(
        data={"filename": filename, "size_bytes": dest.stat().st_size},
        message="Backup created", status_code=201,
    )


@router.get("/{filename}/download")
async def download_backup(filename: str):
    if not _FILENAME_RE.match(filename):
        raise ApiError.bad_request("Invalid backup filename")
    path = BACKUP_DIR / filename
    if not path.is_file():
        raise ApiError.not_found("Backup not found")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


@router.delete("/{filename}", response_model=dict)
async def delete_backup(filename: str):
    if not _FILENAME_RE.match(filename):
        raise ApiError.bad_request("Invalid backup filename")
    path = BACKUP_DIR / filename
    if not path.is_file():
        raise ApiError.not_found("Backup not found")
    path.unlink()
    return success_response(message="Backup deleted")
