const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  aiModel?: string
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, product_model: productModel || null, api_key: apiKey || null, ai_model: aiModel || null }),
  });
  if (!res.ok) {
    throw new Error(`Failed to submit scrape job: ${res.statusText}`);
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<ScrapeStatus> {
  const res = await fetch(`${API_BASE}/api/scrape/${jobId}`);
  if (!res.ok) {
    throw new Error(`Failed to get job status: ${res.statusText}`);
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
    throw new Error(`Failed to submit review: ${res.statusText}`);
  }
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/scrape/${jobId}/download`;
}
