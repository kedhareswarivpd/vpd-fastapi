from app.crud.base import CRUDBase
from app.models.download import Download
from app.schemas.cms import DownloadCreate, DownloadOut, DownloadUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Download, searchable_fields=["title", "category"])

router = build_crud_router(
    crud, DownloadCreate, DownloadUpdate, DownloadOut,
    prefix="/downloads", tags=["Downloads"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["category", "is_published"],
)
