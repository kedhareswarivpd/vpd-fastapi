from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

# Cap for self-service "my own records" list endpoints (e.g. /employees/me/leaves,
# /clients/me/invoices) that intentionally skip full page-param pagination since
# they're already scoped to a single user's own rows. Without *some* limit these
# are unbounded production queries (CF-BE-005) — an account that accumulates years
# of records would return everything in one response. 500 is far above realistic
# usage for any of these resources; raise it (or migrate to real pagination) only
# if a legitimate use case needs more.
SELF_SERVICE_LIST_CAP = 500


def bounded_select(stmt, cap: int = SELF_SERVICE_LIST_CAP):
    """Wrap a self-service "list my own X" query with `.limit(cap)`.

    Exists so a self-service endpoint can't silently forget to bound its
    query (CF-BE-005 / SonarQube L2) — calling `bounded_select(stmt)` instead
    of a bare `stmt.limit(SELF_SERVICE_LIST_CAP)` makes the intent explicit
    at the call site and gives every self-service list endpoint one obvious
    place to apply the cap consistently. Only use this for queries already
    scoped to a single user's own rows (e.g. `WHERE employee_id == me`) that
    intentionally skip full `page_params` pagination; endpoints that accept
    real page/limit params should use `paginate_query`/`page_params` instead.
    """
    return stmt.limit(cap)


class PageParams(BaseModel):
    page: int = 1
    limit: int = 20
    sort: str | None = None
    search: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def page_params(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str | None = Query(None, description="e.g. -created_at,title"),
    search: str | None = Query(None),
) -> PageParams:
    return PageParams(page=page, limit=limit, sort=sort, search=search)


async def paginate_query(db: AsyncSession, stmt, count_stmt, page: PageParams):
    """Execute a pre-filtered `stmt`/`count_stmt` pair with page/limit applied
    and return `(items, meta)`. Extracted from employees.py/training.py, which
    each hand-rolled this same "run paginated select + matching count select +
    build meta" tail independently (CF-BE-006) — building the *filtered*
    `stmt`/`count_stmt` themselves stays per-endpoint since the filter columns
    differ per model; only this identical tail is shared.
    """
    from app.utils.responses import build_pagination_meta

    stmt = stmt.offset(page.offset).limit(page.limit)
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return items, build_pagination_meta(total, page.page, page.limit)


def apply_sort(
    query,
    model,
    sort: str | None,
    default_field: str = "created_at",
    allowed_fields: set[str] | list[str] | None = None,
):
    """Applies `sort=-created_at,title` style ordering to a SQLAlchemy select().

    `allowed_fields`, when given, restricts sorting to that allowlist of
    column-name strings — a requested field that exists on `model` but isn't
    in the allowlist is silently skipped, same as a genuinely bogus field
    name (CF-BE-007). This keeps `sort=` from being usable to probe for the
    existence of columns that were never meant to be client-sortable (e.g.
    password_hash, internal-only fields), while leaving the "unknown field
    silently ignored" behavior unchanged for callers that don't pass one.
    """
    if not sort:
        return query.order_by(getattr(model, default_field).desc())
    for field in sort.split(","):
        field = field.strip()
        if not field:
            continue
        desc = field.startswith("-")
        col_name = field[1:] if desc else field
        if allowed_fields is not None and col_name not in allowed_fields:
            continue
        column = getattr(model, col_name, None)
        if column is None:
            continue
        query = query.order_by(column.desc() if desc else column.asc())
    return query
