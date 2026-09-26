const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

const UNITS: { unit: Intl.RelativeTimeFormatUnit; ms: number }[] = [
  { unit: "year", ms: 365 * DAY_MS },
  { unit: "month", ms: 30 * DAY_MS },
  { unit: "week", ms: 7 * DAY_MS },
  { unit: "day", ms: DAY_MS },
  { unit: "hour", ms: HOUR_MS },
];

// "yesterday" is wanted for one day; "1 week ago" rather than "last week" for the others (DC-14).
const dayFormat = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const otherFormat = new Intl.RelativeTimeFormat("en", { numeric: "always" });

/** FR-010: under one hour "just now", otherwise the largest whole unit. `now` is injected. */
export function formatRelative(at: Date | string, now: Date): string {
  const difference = new Date(at).getTime() - now.getTime();
  if (Math.abs(difference) < HOUR_MS) {
    return "just now";
  }
  for (const { unit, ms } of UNITS) {
    const count = Math.trunc(Math.abs(difference) / ms);
    if (count >= 1) {
      const signed = difference < 0 ? -count : count;
      return (unit === "day" ? dayFormat : otherFormat).format(signed, unit);
    }
  }
  return "just now";
}

/** The absolute date and time in the user's time zone, for a tooltip. */
export function formatAbsolute(at: Date | string, timeZone: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(new Date(at));
}

const regionNames = new Intl.DisplayNames(["en"], { type: "region" });

/** FR-011: a country code with the country's English name. */
export function countryName(code: string): string {
  return regionNames.of(code) ?? code;
}

// Screen labels of frontend Screen labels for the enums whose contexts are unambiguous. Strength
// is left to the task whose contract brings it: its `MEDIUM` is also a weight level.
const LABELS: Record<string, string> = {
  HOT: "Hot",
  WARM: "Warm",
  COLD: "Cold",
  RANKED: "Ranked",
  BELOW_FIT: "Below fit",
  DISQUALIFIED: "Excluded",
  CUSTOMER: "Customer",
  CLASSIFIER: "Quick check",
  LLM: "Detailed check",
};

/** Screen label of a `FindingStrength`; `MEDIUM` reads "Clear" here, though it is a weight level elsewhere. */
export function strengthLabel(value: string): string {
  return value === "MEDIUM" ? "Clear" : enumLabel(value);
}

/** FR-011: the screen label of an enum value, otherwise the value in sentence case. */
export function enumLabel(value: string): string {
  const label = LABELS[value];
  if (label !== undefined) {
    return label;
  }
  const words = value.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
