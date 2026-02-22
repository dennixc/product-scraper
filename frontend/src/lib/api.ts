const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ProductResult {
  product_name: string;
  product_model: string;
  main_images: string[];
  gallery_images: string[];
  summary: string;
  description: string;
  source_url: string;
}

export interface ScrapeStatus {
  job_id: string;
  status: "processing" | "completed" | "failed";
  progress: string | null;
  result: ProductResult | null;
  error: string | null;
}

export async function submitScrapeJob(
  url: string,
  productModel?: string
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, product_model: productModel || null }),
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

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/scrape/${jobId}/download`;
}

export function getImageUrl(jobId: string, filename: string): string {
  return `${API_BASE}/api/scrape/${jobId}/images/${filename}`;
}
