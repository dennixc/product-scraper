"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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

interface ResultPreviewProps {
  result: ProductResult;
  downloadUrl: string;
}

export function ResultPreview({ result, downloadUrl }: ResultPreviewProps) {
  const [htmlView, setHtmlView] = useState<"preview" | "text" | "source">("preview");
  const [shoplineView, setShoplineView] = useState<"preview" | "text" | "source">("preview");
  const [htmlCopied, setHtmlCopied] = useState(false);
  const [shoplineCopied, setShoplineCopied] = useState(false);
  const copyToClipboard = async (text: string, type: "html" | "shopline") => {
    await navigator.clipboard.writeText(text);
    if (type === "html") {
      setHtmlCopied(true);
      setTimeout(() => setHtmlCopied(false), 2000);
    } else {
      setShoplineCopied(true);
      setTimeout(() => setShoplineCopied(false), 2000);
    }
  };

  const [rawHtmlOpen, setRawHtmlOpen] = useState(false);

  return (
    <div className="space-y-4">
      {/* Shopline HTML — Primary output */}
      {!result.description_shopline && result.description_html && (
        <Card>
          <CardContent className="py-6">
            <div className="text-center text-sm text-muted-foreground">
              <p>Shopline HTML 生成失敗，請檢查 API key 或稍後再試。</p>
              <p className="mt-1">你仍然可以喺下方複製原始提取 HTML。</p>
            </div>
          </CardContent>
        </Card>
      )}
      {result.description_shopline && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Shopline HTML</CardTitle>
              <div className="flex items-center gap-2">
                <div className="flex rounded-md border">
                  <button
                    onClick={() => setShoplineView("preview")}
                    className={`px-3 py-1 text-xs font-medium rounded-l-md transition-colors ${
                      shoplineView === "preview"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    預覽
                  </button>
                  <button
                    onClick={() => setShoplineView("text")}
                    className={`px-3 py-1 text-xs font-medium border-x transition-colors ${
                      shoplineView === "text"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    純文字
                  </button>
                  <button
                    onClick={() => setShoplineView("source")}
                    className={`px-3 py-1 text-xs font-medium rounded-r-md transition-colors ${
                      shoplineView === "source"
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
                      shoplineView === "text"
                        ? htmlToText(result.description_shopline)
                        : result.description_shopline,
                      "shopline"
                    )
                  }
                >
                  {shoplineCopied
                    ? "已複製 ✓"
                    : shoplineView === "text"
                      ? "複製文字"
                      : "複製 HTML"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {shoplineView === "preview" ? (
              <div
                dangerouslySetInnerHTML={{ __html: result.description_shopline }}
              />
            ) : shoplineView === "text" ? (
              <div className="text-sm whitespace-pre-wrap p-4 bg-muted rounded-md max-h-96 overflow-y-auto">
                {htmlToText(result.description_shopline)}
              </div>
            ) : (
              <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto whitespace-pre-wrap break-all max-h-96 overflow-y-auto">
                {result.description_shopline}
              </pre>
            )}
          </CardContent>
        </Card>
      )}

      {/* Product Info + Download */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">產品資訊</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-[3rem_1fr] gap-y-2 gap-x-2">
            <span className="text-sm font-medium text-muted-foreground">名稱</span>
            <span className="text-sm">{result.product_name}</span>
            <span className="text-sm font-medium text-muted-foreground">型號</span>
            <span className="text-sm font-mono">{result.product_model}</span>
            <span className="text-sm font-medium text-muted-foreground">來源</span>
            <a href={result.source_url} target="_blank" rel="noopener noreferrer"
              className="text-sm text-primary underline hover:no-underline truncate">
              {result.source_url}
            </a>
          </div>
          <div className="pt-2">
            <a
              href={downloadUrl}
              download
              className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors bg-primary text-primary-foreground shadow hover:bg-primary/90 h-9 px-4 py-2 w-full text-center"
            >
              下載 ZIP
            </a>
          </div>
        </CardContent>
      </Card>

      {/* Raw Description HTML — Collapsible secondary section */}
      {result.description_html && (
        <Collapsible open={rawHtmlOpen} onOpenChange={setRawHtmlOpen}>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CollapsibleTrigger asChild>
                  <button className="flex items-center gap-2 hover:opacity-70 transition-opacity">
                    <svg
                      className={`h-4 w-4 text-muted-foreground transition-transform ${rawHtmlOpen ? "rotate-90" : ""}`}
                      xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                    >
                      <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
                    </svg>
                    <CardTitle className="text-lg text-muted-foreground">原始提取 HTML</CardTitle>
                  </button>
                </CollapsibleTrigger>
                {rawHtmlOpen && (
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
                            : result.description_html,
                          "html"
                        )
                      }
                    >
                      {htmlCopied
                        ? "已複製 ✓"
                        : htmlView === "text"
                          ? "複製文字"
                          : "複製 HTML"}
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CollapsibleContent>
              <CardContent>
                {htmlView === "preview" ? (
                  <div
                    className="prose prose-sm max-w-none dark:prose-invert"
                    dangerouslySetInnerHTML={{ __html: result.description_html }}
                  />
                ) : htmlView === "text" ? (
                  <div className="text-sm whitespace-pre-wrap p-4 bg-muted rounded-md max-h-96 overflow-y-auto">
                    {htmlToText(result.description_html)}
                  </div>
                ) : (
                  <pre className="text-xs bg-muted p-4 rounded-md overflow-x-auto whitespace-pre-wrap break-all max-h-96 overflow-y-auto">
                    {result.description_html}
                  </pre>
                )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      )}
    </div>
  );
}
