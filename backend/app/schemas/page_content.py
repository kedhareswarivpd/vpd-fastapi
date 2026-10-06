from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class PageContentBase(BaseModel):
    slug: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=255)
    content: str | None = None
    is_published: bool = True


class PageContentCreate(PageContentBase):
    pass


class PageContentUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    content: str | None = None
    is_published: bool | None = None


class PageContentOut(PageContentBase, TimestampedRead):
    pass
