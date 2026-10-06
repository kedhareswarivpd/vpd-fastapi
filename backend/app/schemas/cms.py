"""
Schemas for the simpler content/CMS resources (Service, CaseStudy,
Testimonial, Download, Event). Grouped in one module since each follows the
same Create/Update/Out shape as their SQLAlchemy model.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import TimestampedRead


# ---------- Service ----------
class ServiceCreate(BaseModel):
    name: str
    slug: str | None = None
    icon: str | None = None
    overview: str | None = None
    business_problems: str | None = None
    solutions: str | None = None
    features: list[str] = []
    benefits: list[str] = []
    process: list[dict] = []
    technology_stack: list[str] = []
    deliverables: list[str] = []
    related_industries: list[str] = []
    gallery: list[str] = []
    faqs: list[dict] = []
    cover_image: str | None = None
    is_published: bool = True
    order: int = 0


class ServiceUpdate(BaseModel):
    name: str | None = None
    overview: str | None = None
    features: list[str] | None = None
    benefits: list[str] | None = None
    gallery: list[str] | None = None
    faqs: list[dict] | None = None
    is_published: bool | None = None
    order: int | None = None


class ServiceOut(TimestampedRead):
    name: str
    slug: str
    icon: str | None = None
    overview: str | None = None
    business_problems: str | None = None
    solutions: str | None = None
    features: list[str] = []
    benefits: list[str] = []
    process: list[dict] = []
    technology_stack: list[str] = []
    deliverables: list[str] = []
    gallery: list[str] = []
    faqs: list[dict] = []
    cover_image: str | None = None
    is_published: bool
    order: int


# ---------- Case Study ----------
class CaseStudyCreate(BaseModel):
    title: str
    slug: str | None = None
    project_id: uuid.UUID | None = None
    client_name: str | None = None
    industry: str | None = None
    problem: str | None = None
    solution: str | None = None
    implementation: str | None = None
    result: str | None = None
    roi: str | None = None
    customer_feedback: str | None = None
    download_url: str | None = None
    downloads: list[dict] = []
    cover_image: str | None = None
    is_published: bool = True


class CaseStudyUpdate(BaseModel):
    result: str | None = None
    roi: str | None = None
    downloads: list[dict] | None = None
    is_published: bool | None = None


class CaseStudyOut(TimestampedRead):
    title: str
    slug: str
    project_id: uuid.UUID | None = None
    client_name: str | None = None
    industry: str | None = None
    problem: str | None = None
    solution: str | None = None
    implementation: str | None = None
    result: str | None = None
    roi: str | None = None
    customer_feedback: str | None = None
    download_url: str | None = None
    downloads: list[dict] = []
    cover_image: str | None = None
    is_published: bool


# ---------- Testimonial ----------
class TestimonialCreate(BaseModel):
    client_id: uuid.UUID | None = None
    author_name: str
    author_title: str | None = None
    company_name: str | None = None
    avatar: str | None = None
    rating: int = 5
    content: str
    is_published: bool = True


class TestimonialUpdate(BaseModel):
    content: str | None = None
    rating: int | None = None
    is_published: bool | None = None


class TestimonialOut(TimestampedRead):
    client_id: uuid.UUID | None = None
    author_name: str
    author_title: str | None = None
    company_name: str | None = None
    avatar: str | None = None
    rating: int
    content: str
    is_published: bool


# ---------- Download ----------
class DownloadCreate(BaseModel):
    title: str
    description: str | None = None
    file_url: str
    file_type: str | None = None
    category: str | None = None
    requires_lead: bool = False
    is_published: bool = True


class DownloadUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    is_published: bool | None = None


class DownloadOut(TimestampedRead):
    title: str
    description: str | None = None
    file_url: str
    file_type: str | None = None
    category: str | None = None
    download_count: int
    requires_lead: bool
    is_published: bool


# ---------- Event ----------
class EventCreate(BaseModel):
    title: str
    slug: str | None = None
    description: str | None = None
    cover_image: str | None = None
    location: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    is_virtual: bool = False
    registration_url: str | None = None
    is_published: bool = True


class EventUpdate(BaseModel):
    description: str | None = None
    location: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_published: bool | None = None


class EventOut(TimestampedRead):
    title: str
    slug: str
    description: str | None = None
    cover_image: str | None = None
    location: str | None = None
    start_date: datetime
    end_date: datetime | None = None
    is_virtual: bool
    registration_url: str | None = None
    is_published: bool


# ---------- Industry ----------
class IndustryCreate(BaseModel):
    name: str
    slug: str | None = None
    icon: str | None = None
    description: str | None = None
    cover_image: str | None = None
    is_published: bool = True


class IndustryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    cover_image: str | None = None
    is_published: bool | None = None


class IndustryOut(TimestampedRead):
    name: str
    slug: str
    icon: str | None = None
    description: str | None = None
    cover_image: str | None = None
    is_published: bool


# ---------- Technology ----------
class TechnologyCreate(BaseModel):
    name: str
    category: str = "other"
    logo: str | None = None
    description: str | None = None


class TechnologyUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    logo: str | None = None
    description: str | None = None


class TechnologyOut(TimestampedRead):
    name: str
    category: str
    logo: str | None = None
    description: str | None = None


# ---------- Award ----------
class AwardCreate(BaseModel):
    title: str
    issued_by: str | None = None
    year: int | None = None
    image: str | None = None
    description: str | None = None
    is_published: bool = True


class AwardUpdate(BaseModel):
    title: str | None = None
    issued_by: str | None = None
    year: int | None = None
    image: str | None = None
    description: str | None = None
    is_published: bool | None = None


class AwardOut(TimestampedRead):
    title: str
    issued_by: str | None = None
    year: int | None = None
    image: str | None = None
    description: str | None = None
    is_published: bool


# ---------- Announcement ----------
class AnnouncementCreate(BaseModel):
    title: str
    body: str
    order: int = 0
    is_published: bool = True
    expires_at: datetime | None = None


class AnnouncementUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    order: int | None = None
    is_published: bool | None = None
    expires_at: datetime | None = None


class AnnouncementOut(TimestampedRead):
    title: str
    body: str
    order: int
    is_published: bool
    expires_at: datetime | None = None


# ---------- FAQ ----------
class FaqCreate(BaseModel):
    question: str
    answer: str
    category: str = "general"
    order: int = 0
    is_published: bool = True


class FaqUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    order: int | None = None
    is_published: bool | None = None


class FaqOut(TimestampedRead):
    question: str
    answer: str
    category: str
    order: int
    is_published: bool


# ---------- Gallery ----------
class GalleryCreate(BaseModel):
    title: str | None = None
    image_url: str
    type: str = "image"
    project_id: uuid.UUID | None = None
    album_name: str | None = None
    is_published: bool = True


class GalleryUpdate(BaseModel):
    title: str | None = None
    image_url: str | None = None
    type: str | None = None
    album_name: str | None = None
    is_published: bool | None = None


class GalleryOut(TimestampedRead):
    title: str | None = None
    image_url: str
    type: str
    project_id: uuid.UUID | None = None
    album_name: str | None = None
    is_published: bool


# ---------- Portfolio ----------
class PortfolioCreate(BaseModel):
    title: str
    slug: str | None = None
    category: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    live_url: str | None = None
    project_id: uuid.UUID | None = None
    is_featured: bool = False
    order: int = 0


class PortfolioUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    live_url: str | None = None
    is_featured: bool | None = None
    order: int | None = None


class PortfolioOut(TimestampedRead):
    title: str
    slug: str
    category: str | None = None
    thumbnail: str | None = None
    description: str | None = None
    live_url: str | None = None
    project_id: uuid.UUID | None = None
    is_featured: bool
    order: int


# ---------- Partner ----------
class PartnerCreate(BaseModel):
    name: str
    logo: str | None = None
    website: str | None = None
    type: str = "technology_partner"
    is_published: bool = True


class PartnerUpdate(BaseModel):
    name: str | None = None
    logo: str | None = None
    website: str | None = None
    type: str | None = None
    is_published: bool | None = None


class PartnerOut(TimestampedRead):
    name: str
    logo: str | None = None
    website: str | None = None
    type: str
    is_published: bool


# ---------- Leadership ----------
class LeadershipCreate(BaseModel):
    name: str
    title: str
    bio: str | None = None
    photo_url: str | None = None
    linkedin: str | None = None
    order: int = 0
    is_published: bool = True


class LeadershipUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    bio: str | None = None
    photo_url: str | None = None
    linkedin: str | None = None
    order: int | None = None
    is_published: bool | None = None


class LeadershipOut(TimestampedRead):
    name: str
    title: str
    bio: str | None = None
    photo_url: str | None = None
    linkedin: str | None = None
    order: int
    is_published: bool


# ---------- Office ----------
class OfficeCreate(BaseModel):
    city: str
    country: str | None = None
    description: str | None = None
    address: str | None = None
    is_headquarters: bool = False
    order: int = 0
    is_published: bool = True


class OfficeUpdate(BaseModel):
    city: str | None = None
    country: str | None = None
    description: str | None = None
    address: str | None = None
    is_headquarters: bool | None = None
    order: int | None = None
    is_published: bool | None = None


class OfficeOut(TimestampedRead):
    city: str
    country: str | None = None
    description: str | None = None
    address: str | None = None
    is_headquarters: bool
    order: int
    is_published: bool


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name: str
    slug: str | None = None
    type: str = "blog"


class CategoryUpdate(BaseModel):
    name: str | None = None
    type: str | None = None


class CategoryOut(TimestampedRead):
    name: str
    slug: str
    type: str
