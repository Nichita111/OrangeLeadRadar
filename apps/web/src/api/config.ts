/**
 * Loads `/config.json`, written by the `web` container at start-up from the [Runtime]
 * (/architecture/services/frontend.md#runtime) keys the client reads (`API_UPSTREAM` stays
 * server-side, in the container's nginx proxy). The client reads the file before its first
 * render (`main.tsx`); a key missing from the response — the file failed to load, or an older
 * container wrote it before a key existed — falls back to that key's documented default, never a
 * literal invented here.
 */

export interface RuntimeConfig {
  RUN_POLL_INTERVAL_MS: number;
  ALERT_POLL_INTERVAL_MS: number;
  CONFIDENCE_HIGH_MIN: number;
  CONFIDENCE_MEDIUM_MIN: number;
}

export const RUNTIME_CONFIG_DEFAULTS: RuntimeConfig = {
  RUN_POLL_INTERVAL_MS: 2000,
  ALERT_POLL_INTERVAL_MS: 60000,
  CONFIDENCE_HIGH_MIN: 0.85,
  CONFIDENCE_MEDIUM_MIN: 0.65,
};

function isPartialRuntimeConfig(value: unknown): value is Partial<RuntimeConfig> {
  return typeof value === "object" && value !== null;
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  try {
    const response = await fetch("/config.json");
    if (!response.ok) {
      return RUNTIME_CONFIG_DEFAULTS;
    }
    const data: unknown = await response.json();
    if (!isPartialRuntimeConfig(data)) {
      return RUNTIME_CONFIG_DEFAULTS;
    }
    return { ...RUNTIME_CONFIG_DEFAULTS, ...data };
  } catch {
    return RUNTIME_CONFIG_DEFAULTS;
  }
}
