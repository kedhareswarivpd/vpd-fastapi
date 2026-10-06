from app.crud.base import CRUDBase
from app.models.gallery import Gallery
from app.schemas.cms import GalleryCreate, GalleryOut, GalleryUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Gallery, searchable_fields=["title", "album_name"])

router = build_crud_router(
    crud, GalleryCreate, GalleryUpdate, GalleryOut,
    prefix="/gallery", tags=["Gallery"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["project_id", "type", "is_published"],
)
