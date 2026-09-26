/**
 * Pure formatting functions of
 * [Formatting](/architecture/services/frontend.md#formatting): `now` is always injected, never
 * read from the clock inside.
 */

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

/** `FR-010`: a relative age such as "3 days ago", for the given `now`. */
export function relativeAge(date: Date, now: Date): string {
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < MINUTE_MS) {
    return "just now";
  }
  if (diffMs < HOUR_MS) {
    const minutes = Math.floor(diffMs / MINUTE_MS);
    return `${String(minutes)} minute${minutes === 1 ? "" : "s"} ago`;
  }
  if (diffMs < DAY_MS) {
    const hours = Math.floor(diffMs / HOUR_MS);
    return `${String(hours)} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.floor(diffMs / DAY_MS);
  return `${String(days)} day${days === 1 ? "" : "s"} ago`;
}

/** `FR-010`: the absolute date and time in the user's time zone, for a tooltip. */
export function absoluteTooltip(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone,
  }).format(date);
}

/** `FR-010`: ISO-8601 for exports. */
export function isoExport(date: Date): string {
  return date.toISOString();
}

/** `FR-011`: a country code shown with the country's English name. */
export function countryName(countryCode: string): string {
  return new Intl.DisplayNames(["en"], { type: "region" }).of(countryCode) ?? countryCode;
}
