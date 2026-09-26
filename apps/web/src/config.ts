/** The runtime keys of frontend Runtime that reach the client through `/config.json`. */
export interface Config {
  CONFIDENCE_HIGH_MIN: number;
  CONFIDENCE_MEDIUM_MIN: number;
}

function unitInterval(record: Record<string, unknown>, key: keyof Config): number {
  const raw = record[key];
  if (raw === undefined) {
    throw new Error(`config.json has no ${key}.`);
  }
  const value = typeof raw === "string" && raw.trim() !== "" ? Number(raw) : raw;
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`config.json: ${key} must be a number between 0 and 1.`);
  }
  return value;
}

/** Parses the body of `/config.json`; a missing key or a bad value throws, and there is no default. */
export function parseConfig(body: unknown): Config {
  if (typeof body !== "object" || body === null || Array.isArray(body)) {
    throw new Error("config.json is not an object.");
  }
  const record = body as Record<string, unknown>;
  return {
    CONFIDENCE_HIGH_MIN: unitInterval(record, "CONFIDENCE_HIGH_MIN"),
    CONFIDENCE_MEDIUM_MIN: unitInterval(record, "CONFIDENCE_MEDIUM_MIN"),
  };
}

export async function loadConfig(): Promise<Config> {
  const response = await fetch(`${window.location.origin}/config.json`);
  if (!response.ok) {
    throw new Error(
      `config.json could not be loaded: the server answered ${String(response.status)}.`,
    );
  }
  return parseConfig(await response.json());
}
