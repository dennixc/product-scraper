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

export interface ScrapeStatus {
  job_id: string;
  status: "processing" | "awaiting_review" | "completed" | "failed";
  progress: string | null;
  result: ProductResult | null;
  error: string | null;
}

export async function submitScrapeJob(
  url: string,
  productModel?: string,
  apiKey?: string,
  aiModel?: string,
  reasoningEffort?: string
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, product_model: productModel || null, api_key: apiKey || null, ai_model: aiModel || null, reasoning_effort: reasoningEffort || null }),
  });
  if (!res.ok) {
    throw new Error(await extractErrorDetail(res, "提交失敗"));
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
  instructions?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, instructions: instructions || "" }),
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
