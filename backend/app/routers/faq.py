from app.crud.base import CRUDBase
from app.models.faq import Faq
from app.schemas.cms import FaqCreate, FaqOut, FaqUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Faq, searchable_fields=["question"])

router = build_crud_router(
    crud, FaqCreate, FaqUpdate, FaqOut,
    prefix="/faqs", tags=["FAQs"],
    public_read=True, write_roles=["admin", "marketing", "support"],
    allowed_filters=["category", "is_published"],
)
