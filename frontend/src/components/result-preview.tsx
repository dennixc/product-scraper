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

interface ResultPreviewProps {
  result: ProductResult;
  downloadUrl: string;
}

export function ResultPreview({ result, downloadUrl }: ResultPreviewProps) {
  const [descExpanded, setDescExpanded] = useState(false);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Product Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Name
            </span>
            <p className="text-sm">{result.product_name}</p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Model
            </span>
            <p className="text-sm font-mono">{result.product_model}</p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Summary
            </span>
            <p className="text-sm">
              {result.summary || "No summary available."}
            </p>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Description
            </span>
            <div className="text-sm whitespace-pre-wrap">
              {result.description ? (
                <>
                  {descExpanded
                    ? result.description
                    : result.description.slice(0, 300)}
                  {result.description.length > 300 && (
                    <Button
                      variant="link"
                      size="sm"
                      className="px-1 h-auto"
                      onClick={() => setDescExpanded(!descExpanded)}
                    >
                      {descExpanded ? "Show less" : "Show more..."}
                    </Button>
                  )}
                </>
              ) : (
                "No description available."
              )}
            </div>
          </div>
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Source
            </span>
            <p className="text-sm">
              <a
                href={result.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline hover:no-underline"
              >
                {result.source_url}
              </a>
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        <a
          href={downloadUrl}
          download
          className="flex-1 inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors bg-primary text-primary-foreground shadow hover:bg-primary/90 h-9 px-4 py-2 text-center"
        >
          Download ZIP
        </a>
      </div>
    </div>
  );
}
