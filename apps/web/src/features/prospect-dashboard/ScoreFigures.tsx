import { ScoreNumber } from "../../components/score/ScoreNumber";

/** FR-112: Priority larger than Fit and Intent; Fit and Intent each carry a meaning in words. */
export function ScoreFigures({
  priority,
  fit,
  intent,
}: {
  priority: number;
  fit: number;
  intent: number;
}) {
  return (
    <div className="flex flex-col gap-3">
      <ScoreNumber label="Priority" value={priority} size="large" />
      <ScoreNumber label="Fit" value={fit} meaning="How well it matches" />
      <ScoreNumber label="Intent" value={intent} meaning="Recent signals" />
    </div>
  );
}
