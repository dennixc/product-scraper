from pydantic import BaseModel, HttpUrl
from typing import Literal

class ScrapeRequest(BaseModel):
    url: HttpUrl
    product_model: str | None = None

class ProductResult(BaseModel):
    product_name: str
    product_model: str
    main_images: list[str]
    gallery_images: list[str]
    summary: str
    description: str
    source_url: str

class ScrapeStatus(BaseModel):
    job_id: str
    status: Literal["processing", "completed", "failed"]
    progress: str | None = None
    result: ProductResult | None = None
    error: str | None = None
