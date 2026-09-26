import type { Dependency } from "../../api/dependencies";

// Two literal copies, each tied to its owning table by `degradation.test.ts`: the Dependencies
// table of Conventions, and the Screen wording column of Degradation.

/** `UPSTREAM_UNAVAILABLE` plus a `details.dependency` value names a Degradation row. */
export const DEPENDENCY_ROWS: Record<Dependency, string> = {
  DATABASE: "Database",
  CLASSIFIER: "Classifier",
  LLM: "OpenRouter",
  EMBEDDER: "Embedder",
  HUBSPOT: "HubSpot",
};

/** `BUDGET_EXHAUSTED` carries no dependency: its code alone names this row. */
export const BUDGET_ROW = "LLM daily budget reached";

export type ScreenWording =
  { headline: string; stillWorks: string[] } | { headline: string; closing: string };

export const SCREEN_WORDING: Record<string, ScreenWording> = {
  Classifier: {
    headline: "Quick checks are unavailable.",
    stillWorks: [
      "Collecting and preparing new documents",
      "Scores from the signals already found",
      "Every screen",
    ],
  },
  OpenRouter: {
    headline: "The AI service is unavailable.",
    stillWorks: [
      "Collecting and preparing new documents",
      "Scores from the signals already found",
      "Every screen",
    ],
  },
  "LLM daily budget reached": {
    headline: "Today's budget for detailed checks is used up.",
    stillWorks: ["Scores from the signals already found", "Every screen"],
  },
  Embedder: {
    headline: "Text analysis is unavailable.",
    stillWorks: [
      "Scores from the signals already found",
      "Every screen",
      "Try it on short pasted text",
    ],
  },
  HubSpot: { headline: "HubSpot is unavailable.", stillWorks: ["Everything else"] },
  Database: {
    headline: "The database is unavailable.",
    closing: "Nothing works until it is back.",
  },
};

/** The wording for an error's code and dependency; null when no Degradation row applies. */
export function screenWording(
  code: string,
  dependency: Dependency | undefined,
): ScreenWording | null {
  if (code === "BUDGET_EXHAUSTED") {
    return SCREEN_WORDING[BUDGET_ROW] ?? null;
  }
  if (code === "UPSTREAM_UNAVAILABLE" && dependency !== undefined) {
    return SCREEN_WORDING[DEPENDENCY_ROWS[dependency]] ?? null;
  }
  return null;
}
