import type { FindingView } from "../../api/prospectsAndEvidence";
import { Quote } from "../../components/score/Quote";
import { enumLabel } from "../../shell/format";

/** FR-116: a finding's quote with the domain, type and age of its source. */
export function FindingQuote({ finding }: { finding: FindingView }) {
  return (
    <Quote
      text={finding.quote}
      {...(finding.quote_en === null ? {} : { english: finding.quote_en })}
      sourceDomain={new URL(finding.document.url).hostname}
      sourceLabel={enumLabel(finding.document.source_type)}
      at={finding.observed_at}
    />
  );
}
