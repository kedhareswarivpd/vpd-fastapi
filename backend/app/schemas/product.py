from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    tagline: str | None = None
    description: str | None = None
    features: list[str] | None = None
    benefits: list[str] | None = None
    pricing_tiers: list[dict] | None = None
    technology_stack: list[str] | None = None
    use_cases: list[str] | None = None
    cover_image: str | None = None
    icon: str | None = None
    is_published: bool = True
    order: int = 0


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    name: str | None = None
    is_published: bool | None = None


class ProductOut(ProductBase, TimestampedRead):
    slug: str
