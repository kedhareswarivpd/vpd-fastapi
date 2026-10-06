from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    status_code: int = 200
    message: str = "Success"
    data: T | None = None
    meta: PaginationMeta | None = None


def success_response(data: Any = None, message: str = "Success", status_code: int = 200, meta: PaginationMeta | None = None) -> dict:
    return {
        "success": True,
        "status_code": status_code,
        "message": message,
        "data": data,
        "meta": meta,
    }


def build_pagination_meta(total: int, page: int, limit: int) -> PaginationMeta:
    total_pages = (total + limit - 1) // limit if limit else 0
    return PaginationMeta(total=total, page=page, limit=limit, total_pages=total_pages)
