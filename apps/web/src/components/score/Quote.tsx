import { RelativeTime } from "../../shell/RelativeTime";

interface QuoteProps {
  /** Verbatim, never altered (FR-116). */
  text: string;
  /** The English translation, only when the passage is not English. */
  english?: string;
  sourceDomain: string;
  sourceLabel: string;
  at: string;
  now?: Date;
}

export function Quote({ text, english, sourceDomain, sourceLabel, at, now }: QuoteProps) {
  return (
    <figure className="m-0 flex flex-col gap-1 border-l-2 border-border pl-3">
      <blockquote className="m-0">{text}</blockquote>
      {english !== undefined && (
        <p className="m-0 text-text-secondary">English: &ldquo;{english}&rdquo;</p>
      )}
      <figcaption className="text-hint text-text-tertiary">
        {sourceDomain}, {sourceLabel},{" "}
        <RelativeTime at={at} {...(now === undefined ? {} : { now })} />
      </figcaption>
    </figure>
  );
}
