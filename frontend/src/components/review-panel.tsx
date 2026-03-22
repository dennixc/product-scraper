"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { ProductResult } from "@/lib/api";

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

interface ReviewPanelProps {
  result: ProductResult;
  onConfirm: () => void;
  onRefine: (instructions: string) => void;
  isRefining: boolean;
}

export function ReviewPanel({ result, onConfirm, onRefine, isRefining }: ReviewPanelProps) {
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

      {/* Description HTML Preview */}
      {result.description_html && (
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
                        ? htmlToText(result.description_html)
                        : result.description_html
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
                dangerouslySetInnerHTML={{ __html: result.description_html }}
              />
            ) : htmlView === "text" ? (
              <div className="text-sm whitespace-pre-wrap p-4 bg-muted rounded-md max-h-[48rem] overflow-y-auto">
                {htmlToText(result.description_html)}
              </div>
            ) : (
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto whitespace-pre-wrap break-all max-h-[48rem] overflow-y-auto">
                {result.description_html}
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
              onClick={onConfirm}
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
