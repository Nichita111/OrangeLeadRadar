/**
 * `FR-116`: a quote verbatim with a rule at its left, its English translation on the next line
 * when the passage is not English, then its source domain, source type and age.
 */
import { formatAbsoluteDateTime, formatRelativeDate, titleCaseEnum } from "../../shell/formatting";

export interface QuoteProps {
  quote: string;
  quoteEn: string | null;
  url: string;
  sourceType: string;
  observedAt: string;
}

export function Quote({ quote, quoteEn, url, sourceType, observedAt }: QuoteProps) {
  return (
    <blockquote className="border-l-2 border-border pl-3 text-sm text-text">
      <p>&ldquo;{quote}&rdquo;</p>
      {quoteEn !== null && <p className="text-text-secondary">English: &ldquo;{quoteEn}&rdquo;</p>}
      <p className="text-[12.5px] text-text-tertiary">
        {new URL(url).hostname}, {titleCaseEnum(sourceType)},{" "}
        <span title={formatAbsoluteDateTime(observedAt)}>{formatRelativeDate(observedAt)}</span>
      </p>
    </blockquote>
  );
}
