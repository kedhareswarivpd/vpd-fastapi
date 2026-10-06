from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import TimestampedRead


class NewsletterSubscribe(BaseModel):
    email: EmailStr
    name: str | None = Field(None, max_length=150)


class NewsletterOut(TimestampedRead):
    email: str
    name: str | None = None
    is_active: bool
    subscribed_at: datetime
