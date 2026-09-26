import { FlameIcon, SnowflakeIcon, SunIcon } from "@phosphor-icons/react";

import { bandLabel, standingLabel } from "../../shell/labels";
import type { components } from "../../api/schema.gen";

type Band = components["schemas"]["AccountScoreBand"];
type Standing = components["schemas"]["AccountScoreStanding"];

const styles: Record<Band, string> = {
  HOT: "bg-accent text-on-accent",
  WARM: "bg-accent-soft text-accent-ink",
  COLD: "bg-cool-soft text-cool",
};

const icons = { HOT: FlameIcon, WARM: SunIcon, COLD: SnowflakeIcon } satisfies Record<
  Band,
  typeof FlameIcon
>;

export function BandChip({ band }: { band: Band }) {
  const Icon = icons[band];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 ${styles[band]}`}>
      <Icon aria-hidden size={16} />
      {bandLabel(band)}
    </span>
  );
}

export function StandingChip({ standing }: { standing: Exclude<Standing, "RANKED"> }) {
  return (
    <span className="inline-flex rounded-full bg-cool-soft px-2 py-1 text-cool">
      {standingLabel(standing)}
    </span>
  );
}
