"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_KEY_STORAGE_KEY = "gemini_api_key";

interface ScrapeFormProps {
  onSubmit: (url: string, productModel?: string, apiKey?: string) => void;
  isLoading: boolean;
}

export function ScrapeForm({ onSubmit, isLoading }: ScrapeFormProps) {
  const [url, setUrl] = useState("");
  const [productModel, setProductModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(API_KEY_STORAGE_KEY);
    if (saved) setApiKey(saved);
  }, []);

  const handleApiKeyChange = (value: string) => {
    setApiKey(value);
    if (value) {
      localStorage.setItem(API_KEY_STORAGE_KEY, value);
    } else {
      localStorage.removeItem(API_KEY_STORAGE_KEY);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim(), productModel.trim() || undefined, apiKey.trim() || undefined);
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
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
            >
              <svg
                className={`h-3 w-3 transition-transform ${showApiKey ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              AI 內容優化 (optional)
            </button>
            {showApiKey && (
              <div className="space-y-2 pl-4 border-l-2 border-muted">
                <Input
                  id="apiKey"
                  type="password"
                  placeholder="Gemini API Key"
                  value={apiKey}
                  onChange={(e) => handleApiKeyChange(e.target.value)}
                  disabled={isLoading}
                />
                <p className="text-xs text-muted-foreground">
                  提供 Gemini API Key 啟用 AI 內容去重同優化。Key 會儲存喺瀏覽器。
                </p>
              </div>
            )}
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
