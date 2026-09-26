import type { components } from "../../api/schema.gen";

export function BandLegend({
  settings,
}: {
  settings: components["schemas"]["ScoringConfig"]["settings"];
}) {
  return (
    <p>
      Cold below {settings.warm_threshold}; Warm from {settings.warm_threshold}; Hot from{" "}
      {settings.hot_threshold}.
    </p>
  );
}
