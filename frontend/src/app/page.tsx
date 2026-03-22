"use client";

import { useState, useEffect } from "react";
import { ScrapeForm } from "@/components/scrape-form";
import { ResultPreview } from "@/components/result-preview";
import { ReviewPanel } from "@/components/review-panel";
import {
  submitScrapeJob,
  getJobStatus,
  getDownloadUrl,
  submitReview,
  type ScrapeStatus,
} from "@/lib/api";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollTrigger, setPollTrigger] = useState(0);

  const handleSubmit = async (url: string, productModel?: string, apiKey?: string, aiModel?: string) => {
    setIsLoading(true);
    setError(null);
    setStatus(null);
    setJobId(null);

    try {
      const response = await submitScrapeJob(url, productModel, apiKey, aiModel);
      setJobId(response.job_id);
      setPollTrigger((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit job");
      setIsLoading(false);
    }
  };

  // Polling for job status — re-triggers on pollTrigger change
  useEffect(() => {
    if (!jobId || !isLoading) return;

    const interval = setInterval(async () => {
      try {
        const jobStatus = await getJobStatus(jobId);
        setStatus(jobStatus);

        if (
          jobStatus.status === "completed" ||
          jobStatus.status === "failed" ||
          jobStatus.status === "awaiting_review"
        ) {
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
  }, [jobId, pollTrigger, isLoading]);

  const handleConfirm = async () => {
    if (!jobId) return;
    setIsLoading(true);
    setError(null);
    try {
      await submitReview(jobId, "confirm");
      setStatus((prev) => prev ? { ...prev, status: "processing", progress: "正在生成 Shopline HTML..." } : prev);
      setPollTrigger((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm");
      setIsLoading(false);
    }
  };

  const handleRefine = async (instructions: string) => {
    if (!jobId) return;
    setIsLoading(true);
    setError(null);
    try {
      await submitReview(jobId, "refine", instructions);
      setStatus((prev) => prev ? { ...prev, status: "processing", progress: "AI 正在根據指示重新提取..." } : prev);
      setPollTrigger((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refine");
      setIsLoading(false);
    }
  };

  const result = status?.result;
  const isReviewing = status?.status === "awaiting_review" && !!result;
  const isCompleted = status?.status === "completed" && !!result;

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight">
            商品描述提取器
          </h1>
          <p className="mt-2 text-muted-foreground">
            從廠商網站提取商品描述同規格，直接貼入 Shopline。
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
                {status.progress || "處理中..."}
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

        {/* Review Panel — shown when awaiting_review */}
        {isReviewing && result && (
          <ReviewPanel
            result={result}
            onConfirm={handleConfirm}
            onRefine={handleRefine}
            isRefining={isLoading}
          />
        )}

        {/* Final Results — shown when completed */}
        {isCompleted && result && jobId && (
          <ResultPreview
            result={result}
            downloadUrl={getDownloadUrl(jobId)}
          />
        )}
      </div>
    </main>
  );
}
