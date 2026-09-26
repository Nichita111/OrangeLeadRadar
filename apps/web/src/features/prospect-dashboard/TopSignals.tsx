import type { ProspectRow } from "../../api/prospectsAndEvidence";
import { RelativeTime } from "../../shell/RelativeTime";
import { strengthLabel } from "../../shell/format";

/** The strongest signals of a prospect row: question, strength and age. */
export function TopSignals({ signals }: { signals: ProspectRow["top_signals"] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-0.5 p-0 text-hint">
      {signals.map((signal) => (
        <li key={signal.question_key}>
          {signal.question_text}, {strengthLabel(signal.strength)},{" "}
          <RelativeTime at={signal.observed_at} />
        </li>
      ))}
    </ul>
  );
}
