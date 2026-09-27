import { RelativeTime } from "../../shell/RelativeTime";
import { textFragmentUrl } from "./textFragment";

interface QuoteProps {
  /** Verbatim, never altered (FR-116). */
  text: string;
  /** The English translation, only when the passage is not English. */
  english?: string;
  sourceDomain: string;
  sourceLabel: string;
  /** The original page, opened in a new tab at the quoted line (FR-116). */
  sourceUrl: string;
  at: string;
  now?: Date;
}

export function Quote({
  text,
  english,
  sourceDomain,
  sourceLabel,
  sourceUrl,
  at,
  now,
}: QuoteProps) {
  return (
    <figure className="m-0 flex flex-col gap-1 border-l-2 border-border pl-3">
      <blockquote className="m-0">{text}</blockquote>
      {english !== undefined && (
        <p className="m-0 text-text-secondary">English: &ldquo;{english}&rdquo;</p>
      )}
      <figcaption className="text-hint text-text-tertiary">
        {sourceDomain}, {sourceLabel},{" "}
        <RelativeTime at={at} {...(now === undefined ? {} : { now })} /> ·{" "}
        <a
          href={textFragmentUrl(sourceUrl, text)}
          target="_blank"
          rel="noreferrer"
          className="text-accent-ink underline"
        >
          Open original<span aria-hidden> ↗</span>
        </a>
      </figcaption>
    </figure>
  );
}
