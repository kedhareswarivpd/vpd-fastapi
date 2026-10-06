from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class SeoMetadataBase(BaseModel):
    page_path: str = Field(min_length=1, max_length=255)
    title: str | None = Field(None, max_length=160)
    description: str | None = Field(None, max_length=320)
    keywords: str | None = Field(None, max_length=500)
    og_title: str | None = Field(None, max_length=160)
    og_description: str | None = Field(None, max_length=320)
    og_image: str | None = None
    og_type: str = "website"
    canonical_url: str | None = None
    schema_markup: dict | None = None
    no_index: bool = False


class SeoMetadataCreate(SeoMetadataBase):
    pass


class SeoMetadataUpdate(BaseModel):
    title: str | None = Field(None, max_length=160)
    description: str | None = Field(None, max_length=320)
    keywords: str | None = None
    og_title: str | None = Field(None, max_length=160)
    og_description: str | None = Field(None, max_length=320)
    og_image: str | None = None
    og_type: str | None = None
    canonical_url: str | None = None
    schema_markup: dict | None = None
    no_index: bool | None = None


class SeoMetadataOut(SeoMetadataBase, TimestampedRead):
    pass
