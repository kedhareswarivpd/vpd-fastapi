from app.crud.base import CRUDBase
from app.models.page_content import PageContent
from app.schemas.page_content import PageContentCreate, PageContentOut, PageContentUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(PageContent, searchable_fields=["slug", "title"])

# CMS module (PDF: Admin Dashboard -> CMS -> Select Website Section -> Manage
# Corresponding Content -> Save/Update Content). public_read=True since the
# frontend renders these sections for anonymous visitors.
router = build_crud_router(
    crud, PageContentCreate, PageContentUpdate, PageContentOut,
    prefix="/page-content", tags=["CMS"],
    public_read=True, write_roles=["admin", "marketing"],
    allowed_filters=["slug", "is_published"],
)
