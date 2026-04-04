"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { ProductResult } from "@/lib/api";
import { translateResult, type TranslateResponse } from "@/lib/api";

function htmlToText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const blocks = doc.body.querySelectorAll("p, h2, h3, h4, li, tr, td");
  const lines: string[] = [];
  for (const block of blocks) {
    const text = block.textContent?.trim();
    if (text) lines.push(text);
  }
  return lines.join("\n\n");
}

type TranslationState = "original" | "en" | "zh-TW";

interface ReviewPanelProps {
  result: ProductResult;
  jobId: string;
  onConfirm: (descriptionHtml?: string) => void;
  onRefine: (instructions: string) => void;
  isRefining: boolean;
}

export function ReviewPanel({ result, jobId, onConfirm, onRefine, isRefining }: ReviewPanelProps) {
  const [htmlView, setHtmlView] = useState<"preview" | "text" | "source">("preview");
  const [instructions, setInstructions] = useState("");
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRefine = () => {
    if (instructions.trim()) {
      onRefine(instructions.trim());
      setInstructions("");
    }
  };

  // Read API key from localStorage
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [aiModel, setAiModel] = useState<string | null>(null);
  useEffect(() => {
    setApiKey(localStorage.getItem("openrouter_api_key"));
    setAiModel(localStorage.getItem("openrouter_ai_model"));
  }, []);

  // Translation state
  const [translationState, setTranslationState] = useState<TranslationState>("original");
  const [translatedCache, setTranslatedCache] = useState<Record<string, TranslateResponse>>({});
  const [isTranslating, setIsTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);

  const handleTranslate = async (target: TranslationState) => {
    if (target === "original") {
      setTranslationState("original");
      setTranslateError(null);
      return;
    }

    if (translatedCache[target]) {
      setTranslationState(target);
      setTranslateError(null);
      return;
    }

    if (!apiKey) {
      setTranslateError("需要 API key 先可以翻譯");
      return;
    }

    setIsTranslating(true);
    setTranslateError(null);
    try {
      const translated = await translateResult(jobId, target, apiKey, aiModel || undefined);
      setTranslatedCache((prev) => ({ ...prev, [target]: translated }));
      setTranslationState(target);
    } catch (err) {
      setTranslateError(err instanceof Error ? err.message : "翻譯失敗");
    } finally {
      setIsTranslating(false);
    }
  };

  const displayHtml =
    translationState !== "original" && translatedCache[translationState]
      ? translatedCache[translationState].description_html
      : result.description_html;

  return (
    <div className="space-y-4">
      {/* Product Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">產品資訊</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex gap-2">
            <span className="text-sm font-medium text-muted-foreground min-w-[3rem]">名稱</span>
            <span className="text-sm">{result.product_name}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-sm font-medium text-muted-foreground min-w-[3rem]">型號</span>
            <span className="text-sm font-mono">{result.product_model}</span>
          </div>
          <div className="flex gap-2">
            <span className="text-sm font-medium text-muted-foreground min-w-[3rem]">來源</span>
            <a href={result.source_url} target="_blank" rel="noopener noreferrer"
              className="text-sm text-primary underline hover:no-underline truncate">
              {result.source_url}
            </a>
          </div>
        </CardContent>
      </Card>

      {/* Translation toolbar */}
      {apiKey && (
        <Card>
          <CardContent className="py-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium text-muted-foreground">翻譯：</span>
              <div className="flex rounded-md border">
                <button
                  onClick={() => handleTranslate("original")}
                  disabled={isTranslating}
                  className={`px-3 py-1.5 text-sm font-medium rounded-l-md transition-colors ${
                    translationState === "original"
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  } ${isTranslating ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  原文
                </button>
                <button
                  onClick={() => handleTranslate("en")}
                  disabled={isTranslating}
                  className={`px-3 py-1.5 text-sm font-medium border-x transition-colors ${
                    translationState === "en"
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  } ${isTranslating ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  English
                </button>
                <button
                  onClick={() => handleTranslate("zh-TW")}
                  disabled={isTranslating}
                  className={`px-3 py-1.5 text-sm font-medium rounded-r-md transition-colors ${
                    translationState === "zh-TW"
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted"
                  } ${isTranslating ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  繁體中文
                </button>
              </div>
              {isTranslating && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <svg
                    className="animate-spin h-4 w-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  翻譯中...
                </div>
              )}
              {translateError && (
                <span className="text-sm text-destructive">{translateError}</span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Description HTML Preview */}
      {displayHtml && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">提取結果預覽</CardTitle>
              <div className="flex items-center gap-2">
                <div className="flex rounded-md border">
                  <button
                    onClick={() => setHtmlView("preview")}
                    className={`px-3 py-1 text-xs font-medium rounded-l-md transition-colors ${
                      htmlView === "preview"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    預覽
                  </button>
                  <button
                    onClick={() => setHtmlView("text")}
                    className={`px-3 py-1 text-xs font-medium border-x transition-colors ${
                      htmlView === "text"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    純文字
                  </button>
                  <button
                    onClick={() => setHtmlView("source")}
                    className={`px-3 py-1 text-xs font-medium rounded-r-md transition-colors ${
                      htmlView === "source"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    原始碼
                  </button>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    copyToClipboard(
                      htmlView === "text"
                        ? htmlToText(displayHtml)
                        : displayHtml
                    )
                  }
                >
                  {copied
                    ? "已複製 ✓"
                    : htmlView === "text"
                      ? "複製文字"
                      : "複製 HTML"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {htmlView === "preview" ? (
              <div
                className="prose prose-sm max-w-none dark:prose-invert max-h-[48rem] overflow-y-auto"
                dangerouslySetInnerHTML={{ __html: displayHtml }}
              />
            ) : htmlView === "text" ? (
              <div className="text-sm whitespace-pre-wrap p-4 bg-muted rounded-md max-h-[48rem] overflow-y-auto">
                {htmlToText(displayHtml)}
              </div>
            ) : (
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto whitespace-pre-wrap break-all max-h-[48rem] overflow-y-auto">
                {displayHtml}
              </pre>
            )}
          </CardContent>
        </Card>
      )}

      {/* Refine Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">改進提取</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            如果內容有遺漏或需要改進，輸入指示讓 AI 重新提取。確認冇問題就直接生成 Shopline HTML。
          </p>
          <textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="例如：請注意頁面下方嘅規格表、缺少了產品特色部分..."
            className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
            disabled={isRefining}
          />
          <div className="flex gap-3">
            <Button
              onClick={handleRefine}
              variant="outline"
              disabled={isRefining || !instructions.trim()}
              className="flex-1"
            >
              {isRefining ? "重新提取中..." : "重新提取"}
            </Button>
            <Button
              onClick={() => onConfirm(translationState !== "original" ? displayHtml : undefined)}
              disabled={isRefining}
              className="flex-1"
            >
              確認並生成 Shopline HTML
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
