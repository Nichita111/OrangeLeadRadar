/**
 * `FR-010`: dates are shown relative, with the absolute date and time in the user's time zone in
 * a tooltip. A pure function of its inputs ([coding guidelines]
 * (/guidelines/coding.md#purity-idempotency-and-state)); `now` is injected so a test controls it.
 */

function startOfUtcDay(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

export function formatRelativeDate(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const dayDiff = Math.round((startOfUtcDay(now) - startOfUtcDay(then)) / 86_400_000);

  if (dayDiff <= 0) {
    const minuteDiff = Math.floor((now.getTime() - then.getTime()) / 60_000);
    if (minuteDiff < 1) {
      return "just now";
    }
    if (minuteDiff < 60) {
      return minuteDiff === 1 ? "1 minute ago" : `${String(minuteDiff)} minutes ago`;
    }
    return "today";
  }
  if (dayDiff === 1) {
    return "yesterday";
  }
  if (dayDiff < 7) {
    return `${String(dayDiff)} days ago`;
  }
  if (dayDiff < 31) {
    const weeks = Math.floor(dayDiff / 7);
    return weeks === 1 ? "1 week ago" : `${String(weeks)} weeks ago`;
  }
  if (dayDiff < 365) {
    const months = Math.floor(dayDiff / 30);
    return months === 1 ? "1 month ago" : `${String(months)} months ago`;
  }
  const years = Math.floor(dayDiff / 365);
  return years === 1 ? "1 year ago" : `${String(years)} years ago`;
}

export function formatAbsoluteDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" });
}

/** `User.last_login_at` and equivalents are `null` before a first sign-in. */
export function formatLastLogin(iso: string | null, now: Date = new Date()): string {
  return iso === null ? "Never" : formatRelativeDate(iso, now);
}

/** `FR-011`: an enum value with no screen label is shown title-cased. */
export function titleCaseEnum(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
