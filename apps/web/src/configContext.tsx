import { createContext, useContext, type ReactNode } from "react";

import type { Config } from "./config";

const ConfigContext = createContext<Config | null>(null);

export function ConfigProvider({ config, children }: { config: Config; children: ReactNode }) {
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>;
}

export function useConfig(): Config {
  const config = useContext(ConfigContext);
  if (config === null) {
    throw new Error("useConfig needs a ConfigProvider.");
  }
  return config;
}
