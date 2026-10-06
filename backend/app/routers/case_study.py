from slugify import slugify

from app.crud.base import CRUDBase
from app.models.case_study import CaseStudy
from app.schemas.cms import CaseStudyCreate, CaseStudyOut, CaseStudyUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(CaseStudy, searchable_fields=["title", "client_name", "industry"])

router = build_crud_router(
    crud, CaseStudyCreate, CaseStudyUpdate, CaseStudyOut,
    prefix="/case-studies", tags=["Case Studies"],
    public_read=True, write_roles=["admin", "marketing", "project_manager"],
    allowed_filters=["project_id", "is_published"],
    before_create=lambda data, user: {**data, "slug": data.get("slug") or slugify(data["title"])},
)
