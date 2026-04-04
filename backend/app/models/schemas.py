from pydantic import BaseModel, HttpUrl
from typing import Literal

class ScrapeRequest(BaseModel):
    url: HttpUrl
    product_model: str | None = None
    api_key: str | None = None
    ai_model: str | None = None
    reasoning_effort: str | None = None

class ProductResult(BaseModel):
    product_name: str
    product_model: str
    summary: str
    description: str
    description_html: str
    description_shopline: str = ""
    source_url: str

class ScrapeStatus(BaseModel):
    job_id: str
    status: Literal["processing", "awaiting_review", "completed", "failed"]
    progress: str | None = None
    result: ProductResult | None = None
    error: str | None = None

class ReviewAction(BaseModel):
    action: Literal["confirm", "refine"]
    instructions: str = ""
    description_html: str | None = None

class TranslateRequest(BaseModel):
    target_language: Literal["en", "zh-TW"]
    api_key: str
    ai_model: str | None = None

class TranslateResponse(BaseModel):
    description_html: str
    description_shopline: str
