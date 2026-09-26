import type { ScoreView } from "../../../api/prospectsAndEvidence";
import { enumLabel, formatRelative, strengthLabel } from "../../../shell/format";

type QuestionEntry = ScoreView["breakdown"]["intent"]["questions"][number];

function names(keys: string[]): string {
  return keys.map(enumLabel).join(", ");
}

function signal(entry: QuestionEntry, now: Date): string {
  const strength = entry.strength === null ? "" : strengthLabel(entry.strength);
  const age = entry.observed_at === null ? "" : formatRelative(entry.observed_at, now);
  return `${entry.question_text} (${strength}, ${age})`;
}

/**
 * The "In short" paragraph of the Why tab (FR-069): a pure function of the score view, so the
 * screen composes no score of its own. `now` is injected for the ages.
 */
export function inShort(score: Pick<ScoreView, "breakdown">, now: Date): string {
  const { breakdown } = score;
  const parts: string[] = [];

  for (const [label, match] of [
    ["Matches", "MATCH"],
    ["Unknown", "UNKNOWN"],
    ["Does not match", "MISMATCH"],
  ] as const) {
    const keys = breakdown.fit.criteria
      .filter((criterion) => criterion.match === match)
      .map((criterion) => criterion.key);
    if (keys.length > 0) {
      parts.push(`${label}: ${names(keys)}.`);
    }
  }

  const counted = breakdown.intent.questions.filter((entry) => entry.finding_id !== null);
  const positive = counted
    .filter((entry) => entry.polarity === "POSITIVE")
    .sort((a, b) => b.points - a.points)
    .slice(0, 2);
  if (positive.length > 0) {
    parts.push(`Strongest signals: ${positive.map((entry) => signal(entry, now)).join(" and ")}.`);
  }
  const negative = counted.filter((entry) => entry.polarity === "NEGATIVE");
  if (negative.length > 0) {
    parts.push(`Holding back: ${negative.map((entry) => signal(entry, now)).join(" and ")}.`);
  }

  if (breakdown.standing === "BELOW_FIT") {
    parts.push("Below the minimum fit.");
  } else if (breakdown.standing === "DISQUALIFIED") {
    const labels = breakdown.disqualifiers
      .filter((rule) => rule.matched && !rule.overridden)
      .map((rule) => rule.label);
    parts.push(`Excluded by the rule ${labels.join(", ")}.`);
  } else if (breakdown.standing === "CUSTOMER") {
    parts.push("Marked as a customer.");
  }
  return parts.join(" ");
}
