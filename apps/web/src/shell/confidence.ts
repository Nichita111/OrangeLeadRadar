import type { Config } from "../config";

export type ConfidenceWord = "High" | "Medium" | "Low";

/** FR-009: the word for a confidence; the thresholds come from the injected config. */
export function confidenceLabel(
  value: number,
  config: Pick<Config, "CONFIDENCE_HIGH_MIN" | "CONFIDENCE_MEDIUM_MIN">,
): ConfidenceWord {
  if (value >= config.CONFIDENCE_HIGH_MIN) {
    return "High";
  }
  return value >= config.CONFIDENCE_MEDIUM_MIN ? "Medium" : "Low";
}
