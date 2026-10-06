from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class SolutionBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    icon: str | None = None
    overview: str | None = None
    problem_statement: str | None = None
    approach: list[str] | None = None
    outcomes: list[str] | None = None
    related_industries: list[str] | None = None
    related_services: list[str] | None = None
    cover_image: str | None = None
    is_published: bool = True
    order: int = 0


class SolutionCreate(SolutionBase):
    pass


class SolutionUpdate(SolutionBase):
    name: str | None = None
    is_published: bool | None = None


class SolutionOut(SolutionBase, TimestampedRead):
    slug: str
