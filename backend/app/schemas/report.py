import uuid

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedRead


class ReportGenerate(BaseModel):
    title: str = Field(min_length=1)
    report_type: str = Field(min_length=1)
    period: str = Field(min_length=1)
    summary: str | None = None


class ReportOut(TimestampedRead):
    title: str
    report_type: str
    period: str
    generated_by: uuid.UUID | None = None
    file_url: str | None = None
    size_bytes: int | None = None
    summary: str | None = None
