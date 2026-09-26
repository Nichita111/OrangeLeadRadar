/**
 * `FR-111`: a band is a chip with an icon and its label — Hot a filled accent chip with a flame,
 * Warm a soft accent chip with a sun, Cold a cool chip with a snowflake; a standing other than
 * Ranked is a neutral chip with its label and no band.
 */
import { FlameIcon, SnowflakeIcon, SunIcon, type Icon } from "@phosphor-icons/react";

import type { Band, Standing } from "../../api/prospects";
import { BAND_LABELS, STANDING_LABELS } from "../../shell/labels";

const BAND_STYLE: Record<Band, { icon: Icon; classes: string }> = {
  HOT: { icon: FlameIcon, classes: "bg-accent text-on-accent" },
  WARM: { icon: SunIcon, classes: "bg-accent-soft text-accent-ink" },
  COLD: { icon: SnowflakeIcon, classes: "bg-cool-soft text-cool" },
};

const CHIP = "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12.5px] font-medium";

export function BandChip({ standing, band }: { standing: Standing; band: Band | null }) {
  if (standing !== "RANKED" || band === null) {
    return (
      <span className={`${CHIP} bg-page text-text-secondary`}>{STANDING_LABELS[standing]}</span>
    );
  }
  const { icon: BandIcon, classes } = BAND_STYLE[band];
  return (
    <span className={`${CHIP} ${classes}`}>
      <BandIcon size={16} aria-hidden="true" />
      {BAND_LABELS[band]}
    </span>
  );
}
