"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ScrapeFormProps {
  onSubmit: (url: string, productModel?: string) => void;
  isLoading: boolean;
}

export function ScrapeForm({ onSubmit, isLoading }: ScrapeFormProps) {
  const [url, setUrl] = useState("");
  const [productModel, setProductModel] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim(), productModel.trim() || undefined);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Scrape Product Data</CardTitle>
        <CardDescription>
          Paste a product page URL to extract product information and images.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="url" className="text-sm font-medium">
              Product URL
            </label>
            <Input
              id="url"
              type="url"
              placeholder="https://www.asus.com/networking/wifi-routers/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              disabled={isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="model" className="text-sm font-medium">
              Product Model (optional)
            </label>
            <Input
              id="model"
              type="text"
              placeholder="e.g. RT-BE58U"
              value={productModel}
              onChange={(e) => setProductModel(e.target.value)}
              disabled={isLoading}
            />
            <p className="text-xs text-muted-foreground">
              Override auto-detected model number for file naming.
            </p>
          </div>
          <Button
            type="submit"
            disabled={isLoading || !url.trim()}
            className="w-full"
          >
            {isLoading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4"
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
                Processing...
              </>
            ) : (
              "Start Scraping"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
