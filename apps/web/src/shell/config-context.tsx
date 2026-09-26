/**
 * Makes the runtime config `main.tsx` loaded before the first render ([Design]
 * (/architecture/services/frontend.md#design)) reachable from any screen.
 */
import { createContext, useContext, type ReactNode } from "react";

import { RUNTIME_CONFIG_DEFAULTS, type RuntimeConfig } from "../api/config";

const ConfigContext = createContext<RuntimeConfig>(RUNTIME_CONFIG_DEFAULTS);

export function ConfigProvider({ value, children }: { value: RuntimeConfig; children: ReactNode }) {
  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useRuntimeConfig(): RuntimeConfig {
  return useContext(ConfigContext);
}
