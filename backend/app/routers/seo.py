from app.crud.base import CRUDBase
from app.models.seo import SeoMetadata
from app.schemas.seo import SeoMetadataCreate, SeoMetadataOut, SeoMetadataUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(SeoMetadata, searchable_fields=["page_path", "title"])

# public_read=True: the frontend needs this to render <title>/<meta> tags for
# each page without requiring a login.
router = build_crud_router(
    crud, SeoMetadataCreate, SeoMetadataUpdate, SeoMetadataOut,
    prefix="/seo", tags=["SEO"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["page_path"],
)
