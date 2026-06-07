"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type Env = "prod" | "test";

const STORAGE_KEY = "app_env";

interface EnvCtx {
  env: Env;
  setEnv: (e: Env) => void;
}

const EnvContext = createContext<EnvCtx | null>(null);

// One-shot migration: when an existing user first loads after the env split,
// promote their legacy unscoped keys to the prod-scoped variants so they don't
// silently lose their saved brand list / selection.
function migrateLegacyLocalStorage(): void {
  try {
    const legacyPairs: Array<[string, string]> = [
      ["brand_profiles", "brand_profiles_prod"],
      ["selected_brand_id", "selected_brand_id_prod"],
    ];
    for (const [oldKey, newKey] of legacyPairs) {
      const legacy = localStorage.getItem(oldKey);
      if (legacy !== null && localStorage.getItem(newKey) === null) {
        localStorage.setItem(newKey, legacy);
        localStorage.removeItem(oldKey);
      }
    }
  } catch { /* ignore */ }
}

function readSavedEnv(): Env {
  if (typeof window === "undefined") return "prod";
  try {
    migrateLegacyLocalStorage();
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "test" || saved === "prod") return saved;
  } catch { /* ignore */ }
  return "prod";
}

export function EnvProvider({ children }: { children: ReactNode }) {
  // Lazy init so the first client render already reflects the saved env.
  // SSR sees "prod" (no window); React 18 reconciles the difference on hydrate.
  const [env, setEnvState] = useState<Env>(readSavedEnv);

  const setEnv = (e: Env) => {
    setEnvState(e);
    try { localStorage.setItem(STORAGE_KEY, e); } catch { /* ignore */ }
  };

  return <EnvContext.Provider value={{ env, setEnv }}>{children}</EnvContext.Provider>;
}

export function useEnv(): EnvCtx {
  const ctx = useContext(EnvContext);
  if (!ctx) throw new Error("useEnv must be used inside <EnvProvider>");
  return ctx;
}
