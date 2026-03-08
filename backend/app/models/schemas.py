from pydantic import BaseModel, HttpUrl
from typing import Literal

class ScrapeRequest(BaseModel):
    url: HttpUrl
    product_model: str | None = None
    api_key: str | None = None
    ai_model: str | None = None

class ProductResult(BaseModel):
    product_name: str
    product_model: str
    summary: str
    description: str
    description_html: str
    specifications: dict[str, str]
    source_url: str

class ScrapeStatus(BaseModel):
    job_id: str
    status: Literal["processing", "completed", "failed"]
    progress: str | None = None
    result: ProductResult | None = None
    error: str | None = None
