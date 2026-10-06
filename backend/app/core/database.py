import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

# Pin TLS for the managed (Supabase) Postgres connection in non-local
# environments — asyncpg does not default to requiring SSL, and this is the
# credential path to production data (CF-AUD-011).
_ssl_connect_args = {"ssl": "require"} if settings.env.lower() not in {"development", "test", "local"} else {}

# CF-BE-009 root-cause finding (backend/performance/pool_matrix_test.py):
# under concurrency exceeding pool_size+max_overflow, requests queue waiting
# for a connection — a queued request never reaches Postgres, so
# pg_stat_activity looks "not saturated" from the DB side while the
# application is fully pool-bound. Controlled tests: raw asyncpg with a
# matching pool size stayed at ~10ms p95 under the same concurrency that
# produced ~1100ms+ p95 through SQLAlchemy's pool at its old default size —
# proving pool capacity, not Postgres or the network, was the bottleneck.
#
# The PgBouncer branch previously used NullPool, which pays a full new
# connection + auth handshake on *every single request* — measured at
# ~650ms-2s+ per connection in this environment, making it strictly worse
# than normal pooling. NullPool was unnecessary caution: the
# `statement_cache_size=0`/`prepared_statement_cache_size=0` connect_args
# below already disable asyncpg's server-side prepared-statement caching,
# which is what actually makes a *pooled, reused* connection safe to hand
# between different PgBouncer transaction-mode backends (see SQLAlchemy's
# asyncpg + PgBouncer docs) — NullPool was solving a problem the connect_args
# already solved, at a severe latency cost. Verified: app-side QueuePool
# routed through a real PgBouncer container measured ~70ms p95 (warm) at the
# same concurrency where NullPool measured ~2.8s p95.
if settings.db_use_pgbouncer:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.env == "development",
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            **_ssl_connect_args,
        },
    )
else:
    engine = create_async_engine(
        settings.async_database_url,
        echo=settings.env == "development",
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args=_ssl_connect_args,
    )

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all ORM models — adds a UUID PK and timestamps to everything."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
