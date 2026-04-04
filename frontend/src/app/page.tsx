"use client";

import { useState, useEffect, useRef } from "react";
import { ScrapeForm } from "@/components/scrape-form";
import { ResultPreview } from "@/components/result-preview";
import { ReviewPanel } from "@/components/review-panel";
import {
  submitScrapeJob,
  getJobStatus,
  getDownloadUrl,
  submitReview,
  cancelJob,
  type ScrapeStatus,
} from "@/lib/api";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollTrigger, setPollTrigger] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [finalElapsed, setFinalElapsed] = useState<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  // Elapsed timer — ticks every second while loading
  useEffect(() => {
    if (!isLoading) return;
    startTimeRef.current = Date.now();
    setElapsed(0);
    setFinalElapsed(null);
    const timer = setInterval(() => {
      if (startTimeRef.current) {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [isLoading]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}:${sec.toString().padStart(2, "0")}` : `${sec}s`;
  };

  const handleSubmit = async (url: string, productModel?: string, apiKey?: string, aiModel?: string, reasoningEffort?: string) => {
    setIsLoading(true);
    setError(null);
    setStatus(null);
    setJobId(null);
    setFinalElapsed(null);

    try {
      const response = await submitScrapeJob(url, productModel, apiKey, aiModel, reasoningEffort);
      setJobId(response.job_id);
      setPollTrigger((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit job");
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;
    try {
      await cancelJob(jobId);
      setIsLoading(false);
      setError("工作已取消");
      setStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消失敗");
    }
  };

  // Polling for job status — re-triggers on pollTrigger change
  useEffect(() => {
    if (!jobId || !isLoading) return;

    let failCount = 0;
    const maxFails = 5;

    const interval = setInterval(async () => {
      try {
        const jobStatus = await getJobStatus(jobId);
        failCount = 0; // reset on success
        setStatus(jobStatus);

        if (
          jobStatus.status === "completed" ||
          jobStatus.status === "failed" ||
          jobStatus.status === "awaiting_review"
        ) {
          clearInterval(interval);
          if (startTimeRef.current) {
            setFinalElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
          }
          setIsLoading(false);

          if (jobStatus.status === "failed") {
            setError(jobStatus.error || "Scraping failed");
          }
        }
      } catch {
        failCount++;
        if (failCount >= maxFails) {
          clearInterval(interval);
          setIsLoading(false);
          setError("無法連接伺服器，請稍後重試");
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, pollTrigger, isLoading]);

  const handleConfirm = async (descriptionHtml?: string) => {
    if (!jobId) return;
    setIsLoading(true);
    setError(null);
    try {
      await submitReview(jobId, "confirm", undefined, descriptionHtml);
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
            <div className="flex items-center justify-between">
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
                <span className="text-sm tabular-nums text-muted-foreground">
                  {formatTime(elapsed)}
                </span>
              </div>
              <button
                onClick={handleCancel}
                className="text-sm text-muted-foreground hover:text-destructive transition-colors"
              >
                取消
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Elapsed time */}
        {!isLoading && finalElapsed !== null && (
          <div className="mb-6 text-sm text-muted-foreground text-right">
            耗時 {formatTime(finalElapsed)}
          </div>
        )}

        {/* Review Panel — shown when awaiting_review */}
        {isReviewing && result && jobId && (
          <ReviewPanel
            result={result}
            jobId={jobId}
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
            jobId={jobId}
          />
        )}
      </div>
    </main>
  );
}
