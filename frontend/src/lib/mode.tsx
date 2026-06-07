"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Env = "prod" | "test";

const STORAGE_KEY = "app_env";

interface EnvCtx {
  env: Env;
  setEnv: (e: Env) => void;
}

const EnvContext = createContext<EnvCtx | null>(null);

export function EnvProvider({ children }: { children: ReactNode }) {
  const [env, setEnvState] = useState<Env>("prod");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "test" || saved === "prod") setEnvState(saved);
    } catch { /* ignore */ }
  }, []);

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
