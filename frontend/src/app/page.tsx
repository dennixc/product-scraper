"use client";

import { useState, useEffect } from "react";
import { ScrapeForm } from "@/components/scrape-form";
import { ResultPreview } from "@/components/result-preview";
import { ImageGallery } from "@/components/image-gallery";
import {
  submitScrapeJob,
  getJobStatus,
  getDownloadUrl,
  getImageUrl,
  type ScrapeStatus,
} from "@/lib/api";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (url: string, productModel?: string) => {
    setIsLoading(true);
    setError(null);
    setStatus(null);
    setJobId(null);

    try {
      const response = await submitScrapeJob(url, productModel);
      setJobId(response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit job");
      setIsLoading(false);
    }
  };

  // Polling for job status
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const jobStatus = await getJobStatus(jobId);
        setStatus(jobStatus);

        if (jobStatus.status === "completed" || jobStatus.status === "failed") {
          clearInterval(interval);
          setIsLoading(false);

          if (jobStatus.status === "failed") {
            setError(jobStatus.error || "Scraping failed");
          }
        }
      } catch {
        clearInterval(interval);
        setIsLoading(false);
        setError("Failed to check job status");
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [jobId]);

  const result = status?.result;

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight">
            Product Data Scraper
          </h1>
          <p className="mt-2 text-muted-foreground">
            Extract product information and images from manufacturer websites.
          </p>
        </div>

        {/* Form */}
        <div className="mb-6">
          <ScrapeForm onSubmit={handleSubmit} isLoading={isLoading} />
        </div>

        {/* Progress */}
        {isLoading && status && (
          <div className="mb-6 rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <svg
                className="animate-spin h-5 w-5 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <span className="text-sm font-medium">
                {status.progress || "Processing..."}
              </span>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Results */}
        {result && jobId && (
          <div className="space-y-6">
            <ResultPreview
              result={result}
              downloadUrl={getDownloadUrl(jobId)}
            />

            <ImageGallery
              title="Main Images"
              subtitle="800 x 800 px - White background, cropped to square"
              images={result.main_images}
              getImageUrl={(filename) => getImageUrl(jobId, filename)}
            />

            <ImageGallery
              title="Gallery Images"
              subtitle="1280px wide - Original aspect ratio"
              images={result.gallery_images}
              getImageUrl={(filename) => getImageUrl(jobId, filename)}
            />
          </div>
        )}
      </div>
    </main>
  );
}
