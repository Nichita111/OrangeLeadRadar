export function ScoreNumbers({
  priority,
  fit,
  intent,
}: {
  priority: number;
  fit: number;
  intent: number;
}) {
  return (
    <dl className="flex gap-6">
      <div>
        <dt>Priority</dt>
        <dd className="font-mono text-page-title tabular-nums">{priority}</dd>
      </div>
      <div>
        <dt>
          Fit <span className="text-text-secondary">how well it matches</span>
        </dt>
        <dd className="font-mono tabular-nums">{fit}</dd>
      </div>
      <div>
        <dt>
          Intent <span className="text-text-secondary">recent signals</span>
        </dt>
        <dd className="font-mono tabular-nums">{intent}</dd>
      </div>
    </dl>
  );
}
