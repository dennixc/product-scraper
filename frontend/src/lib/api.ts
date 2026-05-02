const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function extractErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (body.detail) return String(body.detail);
  } catch { /* not JSON */ }
  return `${fallback}: ${res.statusText}`;
}

export interface ProductResult {
  product_name: string;
  product_model: string;
  summary: string;
  description: string;
  description_html: string;
  description_shopline: string;
  source_url: string;
}

export interface CompareEngineResult {
  product_name: string;
  product_model: string;
  summary: string;
  description: string;
  description_html: string;
  elapsed_ms: number;
  error: string | null;
}

export interface CompareResult {
  firecrawl: CompareEngineResult | null;
  playwright: CompareEngineResult | null;
  source_url: string;
}

export interface ScrapeStatus {
  job_id: string;
  status: "processing" | "awaiting_review" | "completed" | "failed";
  progress: string | null;
  result: ProductResult | null;
  error: string | null;
  compare_result?: CompareResult | null;
  mode?: "normal" | "compare";
}

export interface BrandProfileData {
  needs_javascript: boolean;
  extraction_strategy: string;
  content_selectors: string[];
  noise_selectors: string[];
  content_structure: string;
  content_language: string;
}

export interface StoredBrandProfile extends BrandProfileData {
  id: string;
  name: string;
  created_at: string;
  sample_urls: string[];
  urls_analyzed: number;
  urls_failed: number;
}

export interface BrandLearnResponse extends BrandProfileData {
  urls_analyzed: number;
  urls_failed: number;
}

export async function listBrands(): Promise<StoredBrandProfile[]> {
  const res = await fetch(`${API_BASE}/api/brands`);
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "讀取品牌失敗"));
  }
  return res.json();
}

export async function saveBrand(profile: StoredBrandProfile): Promise<StoredBrandProfile> {
  const res = await fetch(`${API_BASE}/api/brands`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "儲存品牌失敗"));
  }
  return res.json();
}

export async function deleteBrand(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/brands/${id}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(await extractErrorDetail(res, "刪除品牌失敗"));
  }
}

export async function learnBrand(
  urls: string[],
  apiKey: string,
  aiModel?: string,
  firecrawlApiKey?: string
): Promise<BrandLearnResponse> {
  const res = await fetch(`${API_BASE}/api/brands/learn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      urls,
      api_key: apiKey,
      ai_model: aiModel || null,
      firecrawl_api_key: firecrawlApiKey || null,
    }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "品牌學習失敗"));
  }
  return res.json();
}

export async function submitScrapeJob(
  url: string,
  productModel?: string,
  apiKey?: string,
  aiModel?: string,
  reasoningEffort?: string,
  firecrawlApiKey?: string,
  brandProfile?: BrandProfileData
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      product_model: productModel || null,
      api_key: apiKey || null,
      ai_model: aiModel || null,
      reasoning_effort: reasoningEffort || null,
      firecrawl_api_key: firecrawlApiKey || null,
      brand_profile: brandProfile || null,
    }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "提交失敗"));
  }
  return res.json();
}

export async function submitCompareJob(
  url: string,
  firecrawlApiKey?: string,
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      firecrawl_api_key: firecrawlApiKey || null,
    }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "提交對比失敗"));
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<ScrapeStatus> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}`);
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "取得狀態失敗"));
  }
  return res.json();
}

export async function submitReview(
  jobId: string,
  action: "confirm" | "refine",
  instructions?: string,
  descriptionHtml?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, instructions: instructions || "", description_html: descriptionHtml || null }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "提交審核失敗"));
  }
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/scrape/${jobId}/download`;
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "取消失敗"));
  }
}

export interface TranslateResponse {
  description_html: string;
  description_shopline: string;
}

export async function translateResult(
  jobId: string,
  targetLanguage: "en" | "zh-TW",
  apiKey: string,
  aiModel?: string
): Promise<TranslateResponse> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_language: targetLanguage,
      api_key: apiKey,
      ai_model: aiModel || null,
    }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "翻譯失敗"));
  }
  return res.json();
}
