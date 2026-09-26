import { Tooltip } from "../components/Tooltip";
import { formatAbsolute, formatRelative } from "./format";

interface RelativeTimeProps {
  at: string;
  /** Injected for tests; the edge passes the current time. */
  now?: Date;
}

/** FR-010: relative text, the absolute date and time in the user's time zone in a tooltip. */
export function RelativeTime({ at, now = new Date() }: RelativeTimeProps) {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Tooltip content={formatAbsolute(at, timeZone)}>
      <time dateTime={at}>{formatRelative(at, now)}</time>
    </Tooltip>
  );
}
