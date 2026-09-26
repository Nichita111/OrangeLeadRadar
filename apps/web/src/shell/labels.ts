/**
 * The screen-label maps of
 * [Screen labels](/architecture/services/frontend.md#screen-labels), and the confidence word of
 * `FR-009`. An enum value not in a map is title-cased.
 */

const BAND_LABELS: Record<string, string> = { HOT: "Hot", WARM: "Warm", COLD: "Cold" };

const STANDING_LABELS: Record<string, string> = {
  RANKED: "Ranked",
  BELOW_FIT: "Below fit",
  DISQUALIFIED: "Excluded",
  CUSTOMER: "Customer",
};

const STRENGTH_LABELS: Record<string, string> = {
  WEAK: "Weak",
  MEDIUM: "Clear",
  STRONG: "Strong",
};

const DECIDED_BY_LABELS: Record<string, string> = {
  CLASSIFIER: "Quick check",
  LLM: "Detailed check",
};

const TERM_LABELS: Record<string, string> = {
  finding: "Signal",
  fit_score: "Fit",
  intent_score: "Intent",
  priority_score: "Priority",
  disqualifier: "Exclusion rule",
  disqualifier_override: "Exception",
  discovery_candidate: "Suggested account",
  evaluation_item: "Label",
  evaluation_run: "Quality check",
  scoring_settings: "Scoring",
};

/** Title-cases an enum value not covered by a screen-label map, e.g. `NOT_CONFIGURED` → "Not configured". */
export function titleCaseFallback(value: string): string {
  const words = value.toLowerCase().split("_");
  return words.map((word, index) => (index === 0 ? capitalize(word) : word)).join(" ");
}

function capitalize(word: string): string {
  return word.length === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1);
}

export function bandLabel(band: string): string {
  return BAND_LABELS[band] ?? titleCaseFallback(band);
}

export function standingLabel(standing: string): string {
  return STANDING_LABELS[standing] ?? titleCaseFallback(standing);
}

export function strengthLabel(strength: string): string {
  return STRENGTH_LABELS[strength] ?? titleCaseFallback(strength);
}

export function decidedByLabel(decidedBy: string): string {
  return DECIDED_BY_LABELS[decidedBy] ?? titleCaseFallback(decidedBy);
}

export function termLabel(term: string): string {
  return TERM_LABELS[term] ?? titleCaseFallback(term);
}

export type ConfidenceWord = "High" | "Medium" | "Low";

/** `FR-009`: High at `highMin` or above, Medium at `mediumMin` or above, Low below. */
export function confidenceWord(
  confidence: number,
  highMin: number,
  mediumMin: number,
): ConfidenceWord {
  if (confidence >= highMin) {
    return "High";
  }
  if (confidence >= mediumMin) {
    return "Medium";
  }
  return "Low";
}
