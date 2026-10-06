"""Schema for the singleton site-content endpoints (company info, about-page
content) — both are stored as free-form JSON `value` blobs on the existing
`Setting` model (key="company_info" / "about_content"), so a single generic
upsert shape covers both instead of a dedicated Create/Update/Out per field."""
from typing import Any

from pydantic import BaseModel


class SiteContentUpsert(BaseModel):
    value: Any
