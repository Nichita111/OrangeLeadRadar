import type { Schemas } from "../../../api/contract";

type ScoringSettings = Schemas["ScoringSettings"];
type ICPCriterion = Schemas["ICPCriterion"];
type Industry = Schemas["Industry"];
type Market = Schemas["Market"];

/** FR-028: whether the working copy differs from the base version. */
export function settingsChanged(base: ScoringSettings, working: ScoringSettings): boolean {
  return JSON.stringify(base) !== JSON.stringify(working);
}

const FIT_SHARE_CHOICES = [30, 40, 50, 60];

/**
 * FR-151 (G3): the segmented choice's values — 30, 40, 50 and 60 %, plus the stored `fit_weight`
 * (as a percentage) when it is none of those, so it still shows as a selected choice.
 */
export function fitShareChoices(storedFitWeight: number): number[] {
  const stored = Math.round(storedFitWeight * 100);
  return FIT_SHARE_CHOICES.includes(stored)
    ? [...FIT_SHARE_CHOICES]
    : [...FIT_SHARE_CHOICES, stored].sort((a, b) => a - b);
}

/**
 * FR-030: `market.country_codes` merged into `values`, without duplicates and keeping `values`'
 * order — the market shortcut that expands to its country codes.
 */
export function addMarketCountries(values: readonly string[], market: Market): string[] {
  const merged = [...values];
  for (const code of market.country_codes) {
    if (!merged.includes(code)) {
      merged.push(code);
    }
  }
  return merged;
}

/**
 * FR-030: the `INDUSTRY` criteria's values that name an industry retired since the active
 * version was saved — the codes the ICP section marks Retired and blocks Save draft on.
 */
export function retiredIndustryCodes(
  criteria: readonly ICPCriterion[],
  industries: readonly Industry[],
): string[] {
  const retired = new Set(
    industries.filter((industry) => industry.status !== "ACTIVE").map((industry) => industry.code),
  );
  const found = new Set<string>();
  for (const criterion of criteria) {
    if (criterion.kind !== "INDUSTRY") {
      continue;
    }
    for (const value of criterion.values ?? []) {
      if (retired.has(value)) {
        found.add(value);
      }
    }
  }
  return [...found];
}

/**
 * FR-031: the Signals row's `half_life_days` placeholder — the source-type defaults of the
 * question, one number when they agree, else each distinct default.
 */
export function halfLifePlaceholder(
  sourceTypes: readonly string[],
  defaultHalfLifeDays: Record<string, number>,
): string {
  const distinct = [...new Set(sourceTypes.map((type) => defaultHalfLifeDays[type]))];
  return distinct.join(" / ");
}
