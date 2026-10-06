from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ResourceBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    resource_type: str = "guide"
    description: str | None = None
    file_url: str | None = None
    cover_image: str | None = None
    is_published: bool = True


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(ResourceBase):
    title: str | None = None
    is_published: bool | None = None


class ResourceOut(ResourceBase, TimestampedRead):
    slug: str
    download_count: int
