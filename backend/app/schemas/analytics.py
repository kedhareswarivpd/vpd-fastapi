from pydantic import BaseModel


class PageViewCreate(BaseModel):
    path: str
    ip_address: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    country: str | None = None


class PageViewStats(BaseModel):
    path: str
    count: int


class AnalyticsSummary(BaseModel):
    total_views: int
    unique_paths: int
    top_pages: list[PageViewStats]
