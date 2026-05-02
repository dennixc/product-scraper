from pydantic import BaseModel, HttpUrl
from typing import Literal


class BrandProfile(BaseModel):
    needs_javascript: bool = False
    extraction_strategy: str = "rule_based"
    content_selectors: list[str] = []
    noise_selectors: list[str] = []
    content_structure: str = "mixed"
    content_language: str = ""


class ScrapeRequest(BaseModel):
    url: HttpUrl
    product_model: str | None = None
    api_key: str | None = None
    ai_model: str | None = None
    reasoning_effort: str | None = None
    firecrawl_api_key: str | None = None
    brand_profile: BrandProfile | None = None

class ProductResult(BaseModel):
    product_name: str
    product_model: str
    summary: str
    description: str
    description_html: str
    description_shopline: str = ""
    source_url: str

class CompareEngineResult(BaseModel):
    product_name: str = ""
    product_model: str = ""
    summary: str = ""
    description: str = ""
    description_html: str = ""
    elapsed_ms: int = 0
    error: str | None = None


class CompareResult(BaseModel):
    firecrawl: CompareEngineResult | None = None
    playwright: CompareEngineResult | None = None
    source_url: str


class CompareRequest(BaseModel):
    url: HttpUrl
    firecrawl_api_key: str | None = None


class ScrapeStatus(BaseModel):
    job_id: str
    status: Literal["processing", "awaiting_review", "completed", "failed"]
    progress: str | None = None
    result: ProductResult | None = None
    error: str | None = None
    compare_result: CompareResult | None = None
    mode: Literal["normal", "compare"] = "normal"

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


class BrandLearnRequest(BaseModel):
    urls: list[HttpUrl]
    api_key: str
    ai_model: str | None = None
    firecrawl_api_key: str | None = None


class BrandLearnResponse(BaseModel):
    needs_javascript: bool
    extraction_strategy: str
    content_selectors: list[str]
    noise_selectors: list[str]
    content_structure: str
    content_language: str
    urls_analyzed: int
    urls_failed: int


class StoredBrandProfile(BrandProfile):
    id: str
    name: str
    created_at: str
    sample_urls: list[str] = []
    urls_analyzed: int = 0
    urls_failed: int = 0
