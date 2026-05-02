"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  learnBrand,
  listBrands,
  saveBrand,
  deleteBrand,
  type StoredBrandProfile,
  type BrandProfileData,
} from "@/lib/api";

const STORAGE_KEY = "brand_profiles";
const SELECTED_KEY = "selected_brand_id";

function loadProfiles(): StoredBrandProfile[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveProfiles(profiles: StoredBrandProfile[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profiles));
}

export function getSelectedProfile(): BrandProfileData | null {
  try {
    const id = localStorage.getItem(SELECTED_KEY);
    if (!id) return null;
    const profiles = loadProfiles();
    const p = profiles.find((b) => b.id === id);
    if (!p) return null;
    return {
      needs_javascript: p.needs_javascript,
      extraction_strategy: p.extraction_strategy,
      content_selectors: p.content_selectors,
      noise_selectors: p.noise_selectors,
      content_structure: p.content_structure,
      content_language: p.content_language,
    };
  } catch {
    return null;
  }
}

interface BrandManagerProps {
  apiKey: string;
  aiModel?: string;
  firecrawlApiKey?: string;
  selectedBrandId: string;
  onBrandChange: (brandId: string) => void;
}

export function BrandManager({
  apiKey,
  aiModel,
  firecrawlApiKey,
  selectedBrandId,
  onBrandChange,
}: BrandManagerProps) {
  const [profiles, setProfiles] = useState<StoredBrandProfile[]>([]);
  const [showManager, setShowManager] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrls, setNewUrls] = useState("");
  const [isLearning, setIsLearning] = useState(false);
  const [learnError, setLearnError] = useState<string | null>(null);
  const [learnSuccess, setLearnSuccess] = useState<string | null>(null);
  const [syncWarning, setSyncWarning] = useState<string | null>(null);

  useEffect(() => {
    setProfiles(loadProfiles());
    listBrands()
      .then((remote) => {
        setProfiles(remote);
        saveProfiles(remote);
        setSyncWarning(null);
      })
      .catch(() => {
        setSyncWarning("後端同步失敗，使用本機緩存。新增/刪除可能未同步到雲端。");
      });
  }, []);

  const handleSelectBrand = (id: string) => {
    onBrandChange(id);
    if (id) {
      localStorage.setItem(SELECTED_KEY, id);
    } else {
      localStorage.removeItem(SELECTED_KEY);
    }
  };

  const handleLearn = async () => {
    const urls = newUrls
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.startsWith("http"));

    if (!newName.trim()) {
      setLearnError("請輸入品牌名稱");
      return;
    }
    if (urls.length < 1) {
      setLearnError("請輸入至少 1 條有效 URL");
      return;
    }
    if (!apiKey) {
      setLearnError("需要 OpenRouter API Key 先可以學習品牌");
      return;
    }

    setIsLearning(true);
    setLearnError(null);
    setLearnSuccess(null);

    try {
      const result = await learnBrand(urls, apiKey, aiModel, firecrawlApiKey);

      const profile: StoredBrandProfile = {
        id: crypto.randomUUID(),
        name: newName.trim(),
        created_at: new Date().toISOString(),
        sample_urls: urls,
        ...result,
      };

      const updated = [...profiles.filter((p) => p.name !== profile.name), profile];
      setProfiles(updated);
      saveProfiles(updated);
      handleSelectBrand(profile.id);
      setNewName("");
      setNewUrls("");

      let saveWarning = "";
      try {
        await saveBrand(profile);
        setSyncWarning(null);
      } catch (err) {
        saveWarning = `（雲端同步失敗：${err instanceof Error ? err.message : "未知錯誤"}）`;
        setSyncWarning("品牌已儲存喺本機，但同步到後端失敗。");
      }

      setLearnSuccess(
        `${profile.name} 學習完成！分析咗 ${result.urls_analyzed} 個頁面` +
          (result.urls_failed > 0 ? `（${result.urls_failed} 個失敗）` : "") +
          saveWarning
      );
    } catch (err) {
      setLearnError(err instanceof Error ? err.message : "學習失敗");
    } finally {
      setIsLearning(false);
    }
  };

  const handleDelete = async (id: string) => {
    const updated = profiles.filter((p) => p.id !== id);
    setProfiles(updated);
    saveProfiles(updated);
    if (selectedBrandId === id) {
      handleSelectBrand("");
    }
    try {
      await deleteBrand(id);
      setSyncWarning(null);
    } catch (err) {
      setSyncWarning(
        `本機刪除成功，但同步到後端失敗：${err instanceof Error ? err.message : "未知錯誤"}`
      );
    }
  };

  return (
    <div className="space-y-3">
      {/* Brand selector */}
      <div className="space-y-1.5">
        <label htmlFor="brand" className="text-sm font-medium">
          品牌 Profile
        </label>
        <div className="flex gap-2">
          <select
            id="brand"
            value={selectedBrandId}
            onChange={(e) => handleSelectBrand(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="">自動偵測（唔使用 Profile）</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowManager(!showManager)}
            className="shrink-0"
          >
            {showManager ? "收起" : "管理"}
          </Button>
        </div>
        {selectedBrandId && (
          <p className="text-xs text-muted-foreground">
            將使用已學習嘅品牌結構，跳過 AI 頁面分析步驟
          </p>
        )}
        {syncWarning && (
          <p className="text-xs text-amber-600 dark:text-amber-400">{syncWarning}</p>
        )}
      </div>

      {/* Brand manager panel */}
      {showManager && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">品牌管理</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Existing profiles */}
            {profiles.length > 0 && (
              <div className="space-y-2">
                {profiles.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between rounded-md border px-3 py-2"
                  >
                    <div className="min-w-0">
                      <span className="text-sm font-medium">{p.name}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {p.sample_urls.length} URLs
                        {" | "}
                        {new Date(p.created_at).toLocaleDateString("zh-TW")}
                      </span>
                      {p.content_selectors.length > 0 && (
                        <p className="text-xs text-muted-foreground truncate">
                          Selectors: {p.content_selectors.slice(0, 3).join(", ")}
                          {p.content_selectors.length > 3 && "..."}
                        </p>
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(p.id)}
                      className="shrink-0 text-destructive hover:text-destructive"
                    >
                      刪除
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {/* Add new brand */}
            <div className="space-y-2 border-t pt-3">
              <p className="text-sm font-medium">新增品牌</p>
              <Input
                placeholder="品牌名稱（例如 ASUS）"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                disabled={isLearning}
              />
              <textarea
                placeholder={"貼上產品頁面 URL，每行一條\nhttps://www.example.com/product-1\nhttps://www.example.com/product-2"}
                value={newUrls}
                onChange={(e) => setNewUrls(e.target.value)}
                disabled={isLearning}
                rows={5}
                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
              />
              <Button
                type="button"
                onClick={handleLearn}
                disabled={isLearning || !apiKey}
                className="w-full"
              >
                {isLearning ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-4 w-4"
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
                    學習中...
                  </span>
                ) : (
                  "開始學習"
                )}
              </Button>
              {!apiKey && (
                <p className="text-xs text-muted-foreground">
                  需要先設定 OpenRouter API Key
                </p>
              )}
              {learnError && (
                <p className="text-sm text-destructive">{learnError}</p>
              )}
              {learnSuccess && (
                <p className="text-sm text-green-600 dark:text-green-400">
                  {learnSuccess}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
