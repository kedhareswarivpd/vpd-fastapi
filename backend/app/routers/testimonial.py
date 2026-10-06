from app.crud.base import CRUDBase
from app.models.testimonial import Testimonial
from app.schemas.cms import TestimonialCreate, TestimonialOut, TestimonialUpdate
from app.utils.router_factory import build_crud_router

crud = CRUDBase(Testimonial, searchable_fields=["author_name", "company_name"])

router = build_crud_router(
    crud, TestimonialCreate, TestimonialUpdate, TestimonialOut,
    prefix="/testimonials", tags=["Testimonials"],
    public_read=True, write_roles=["admin", "marketing", "sales"],
    allowed_filters=["client_id", "is_published"],
)
