import { FlameIcon, SnowflakeIcon, SunIcon } from "@phosphor-icons/react";

import { Chip } from "../Chip";
import { enumLabel } from "../../shell/format";
import type { Schemas } from "../../api/contract";

type Band = Schemas["AccountScoreBand"];
type Standing = Schemas["AccountScoreStanding"];

const icons = { HOT: FlameIcon, WARM: SunIcon, COLD: SnowflakeIcon } satisfies Record<
  Band,
  typeof FlameIcon
>;
const tones = { HOT: "accentFilled", WARM: "accent", COLD: "cool" } as const satisfies Record<
  Band,
  "accentFilled" | "accent" | "cool"
>;

/** `FR-111`: Hot a filled accent chip with a flame, Warm a soft accent chip with a sun, Cold a
 * cool chip with a snowflake. */
export function BandChip({ band }: { band: Band }) {
  const Icon = icons[band];
  return (
    <Chip tone={tones[band]}>
      <Icon aria-hidden weight="fill" size={16} />
      {enumLabel(band)}
    </Chip>
  );
}

/** `FR-111`: a standing other than Ranked is a neutral chip with its label and no band. */
export function StandingChip({ standing }: { standing: Exclude<Standing, "RANKED"> }) {
  return <Chip tone="neutral">{enumLabel(standing)}</Chip>;
}
