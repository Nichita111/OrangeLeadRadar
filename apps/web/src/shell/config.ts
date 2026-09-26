import { createContext, useContext } from "react";

/**
 * The keys of [Runtime](/architecture/services/frontend.md#runtime) the client reads at run
 * time, loaded from `/config.json` before the first render
 * ([frontend Design](/architecture/services/frontend.md#design)). `DEMO_SIGN_IN` is declared but
 * first read in a later task ([Runtime](/architecture/services/frontend.md#runtime)).
 */
export interface ClientConfig {
  RUN_POLL_INTERVAL_MS: number;
  ALERT_POLL_INTERVAL_MS: number;
  CONFIDENCE_HIGH_MIN: number;
  CONFIDENCE_MEDIUM_MIN: number;
  MOCK_API: boolean;
}

const NUMBER_KEYS = [
  "RUN_POLL_INTERVAL_MS",
  "ALERT_POLL_INTERVAL_MS",
  "CONFIDENCE_HIGH_MIN",
  "CONFIDENCE_MEDIUM_MIN",
] as const;

const BOOLEAN_KEYS = ["MOCK_API"] as const;

/**
 * Parses `/config.json` into a typed `ClientConfig`. A missing or ill-typed key throws, naming
 * the key ([coding Errors](/guidelines/coding.md#errors)): there is no fallback.
 */
export function parseClientConfig(raw: unknown): ClientConfig {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("/config.json is not a JSON object");
  }
  const record = raw as Record<string, unknown>;

  for (const key of NUMBER_KEYS) {
    if (typeof record[key] !== "number") {
      throw new Error(`/config.json is missing or has a non-numeric key: ${key}`);
    }
  }
  for (const key of BOOLEAN_KEYS) {
    if (typeof record[key] !== "boolean") {
      throw new Error(`/config.json is missing or has a non-boolean key: ${key}`);
    }
  }

  return {
    RUN_POLL_INTERVAL_MS: record.RUN_POLL_INTERVAL_MS as number,
    ALERT_POLL_INTERVAL_MS: record.ALERT_POLL_INTERVAL_MS as number,
    CONFIDENCE_HIGH_MIN: record.CONFIDENCE_HIGH_MIN as number,
    CONFIDENCE_MEDIUM_MIN: record.CONFIDENCE_MEDIUM_MIN as number,
    MOCK_API: record.MOCK_API as boolean,
  };
}

/** Fetches and parses `/config.json`. Thrown errors are not caught: there is no fallback. */
export async function loadClientConfig(): Promise<ClientConfig> {
  const response = await fetch("/config.json");
  if (!response.ok) {
    throw new Error(`/config.json answered ${String(response.status)}`);
  }
  return parseClientConfig(await response.json());
}

const ConfigContext = createContext<ClientConfig | null>(null);

export const ConfigProvider = ConfigContext.Provider;

/** The loaded `ClientConfig`, provided by `ConfigProvider` before the shell renders. */
export function useConfig(): ClientConfig {
  const config = useContext(ConfigContext);
  if (config === null) {
    throw new Error("useConfig() called outside ConfigProvider");
  }
  return config;
}
