import type { components } from "../../api/schema.gen";
import { absoluteTooltip, relativeAge } from "../../shell/formatting";
import { Tooltip } from "../ui/tooltip";
import { Confidence } from "./Confidence";

type Finding = components["schemas"]["FindingView"];
export function QuoteBlock({ finding, now }: { finding: Finding; now: Date }) {
  const domain = new URL(finding.document.url).hostname;
  const observedAt = new Date(finding.observed_at);
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <blockquote className="border-l-2 border-accent pl-3">
      <p>{finding.quote}</p>
      {finding.quote_en && finding.quote_en !== finding.quote ? (
        <p>English: {finding.quote_en}</p>
      ) : null}
      <footer className="text-text-tertiary">
        {domain}, {finding.document.source_type.toLowerCase().replaceAll("_", " ")},{" "}
        <Tooltip label={absoluteTooltip(observedAt, timeZone)}>
          <time dateTime={finding.observed_at}>{relativeAge(observedAt, now)}</time>
        </Tooltip>
        {", "}
        <Confidence value={finding.confidence} />
      </footer>
    </blockquote>
  );
}
