import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base for all 'read' schemas — enables Pydantic to build from SQLAlchemy ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
