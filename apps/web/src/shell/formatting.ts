/**
 * `FR-010`: dates are shown relative, with the absolute date and time in the user's time zone in
 * a tooltip. A pure function of its inputs ([coding guidelines]
 * (/guidelines/coding.md#purity-idempotency-and-state)); `now` is injected so a test controls it.
 */
import type { RuntimeConfig } from "../api/config";

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

/** [Screen labels](/architecture/services/frontend.md#screen-labels): a `FindingStrength` value,
 * including `NONE` for a signal question's Choice options. */
const STRENGTH_LABELS: Record<string, string> = {
  NONE: "None",
  WEAK: "Weak",
  MEDIUM: "Clear",
  STRONG: "Strong",
};

export function strengthLabel(value: string): string {
  return STRENGTH_LABELS[value] ?? titleCaseEnum(value);
}

/**
 * `FR-011`: a country code is shown with its English name. No store table lists valid country
 * codes ([`account`](/architecture/sql-store.md#account) `country_code` is a free ISO 3166-1
 * alpha-2 string), so the client reads the browser's own locale data rather than holding a copy.
 */
export function formatCountryName(code: string): string {
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

/** Every region code the browser's locale data knows, for a country filter's options. */
export function listCountryCodes(): string[] {
  try {
    const supported = Intl.supportedValuesOf as unknown as ((key: string) => string[]) | undefined;
    return (supported?.("region") ?? []).filter((code) => /^[A-Z]{2}$/.test(code));
  } catch {
    return [];
  }
}

/** A run's duration so far, or its final duration once `finishedAt` is set. */
export function formatDuration(
  startedAt: string | null,
  finishedAt: string | null,
  now: Date = new Date(),
): string {
  if (startedAt === null) {
    return "—";
  }
  const end = finishedAt !== null ? new Date(finishedAt) : now;
  const totalSeconds = Math.max(
    0,
    Math.round((end.getTime() - new Date(startedAt).getTime()) / 1000),
  );
  if (totalSeconds < 60) {
    return `${String(totalSeconds)}s`;
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) {
    return seconds === 0 ? `${String(minutes)}m` : `${String(minutes)}m ${String(seconds)}s`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes === 0
    ? `${String(hours)}h`
    : `${String(hours)}h ${String(remainingMinutes)}m`;
}

/** `FR-009`: a confidence as a word; the number belongs only in a tooltip. */
export function confidenceWord(
  value: number,
  config: Pick<RuntimeConfig, "CONFIDENCE_HIGH_MIN" | "CONFIDENCE_MEDIUM_MIN">,
): "High" | "Medium" | "Low" {
  if (value >= config.CONFIDENCE_HIGH_MIN) {
    return "High";
  }
  return value >= config.CONFIDENCE_MEDIUM_MIN ? "Medium" : "Low";
}

/** A criterion has no label: its key in sentence case ([Score breakdown]
 * (/architecture/rules.md#score-breakdown)). */
export function sentenceCaseKey(key: string): string {
  const words = key.toLowerCase().replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
