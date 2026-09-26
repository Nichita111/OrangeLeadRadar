/**
 * `FR-112`: Priority as a number in the mono face, larger than Fit and Intent; Fit and Intent
 * each carry a one-line meaning in words (WF-24, WF-25).
 */
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
    <div className="flex flex-col gap-1">
      <p className="text-sm text-text-secondary">
        Priority <span className="font-mono text-[24px] font-semibold text-text">{priority}</span>
      </p>
      <p className="text-sm text-text-secondary">
        <span className="font-mono font-medium text-text">{fit}</span>{" "}
        <span>Fit, how well it matches</span>
      </p>
      <p className="text-sm text-text-secondary">
        <span className="font-mono font-medium text-text">{intent}</span>{" "}
        <span>Intent, recent signals</span>
      </p>
    </div>
  );
}
