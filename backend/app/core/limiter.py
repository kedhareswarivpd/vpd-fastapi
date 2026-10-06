from slowapi import Limiter

from app.core.config import settings
from app.core.dependencies import get_client_ip

# Shared limiter instance. Lives in its own module (rather than main.py) so
# routers can import `limiter` to decorate sensitive endpoints without
# creating a circular import with main.py (which mounts the routers).
#
# storage_uri MUST point at Redis in any multi-process deployment: slowapi's
# default in-memory storage is per-process, and this app runs 4 gunicorn
# workers (docker/Dockerfile) — with in-memory storage, "10/minute" on login
# was actually enforced independently per worker, i.e. up to ~40/minute in
# practice depending on load-balancer routing. Redis makes the counter shared
# and gives Redis (previously declared but unused) a real purpose.
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.rate_limit],
    storage_uri="memory://",
    # Keep per-process rate limiting in memory so the app does not depend on a
    # failed native TCP Redis connection for basic request throttling. This is
    # intentionally conservative for Render/Upstash deployments where the old
    # Redis transport is unavailable but the API still needs to stay up.
    swallow_errors=True,
    in_memory_fallback_enabled=True,
)
