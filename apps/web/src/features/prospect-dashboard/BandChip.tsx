import { FlameIcon, SnowflakeIcon, SunIcon } from "@phosphor-icons/react";

import type { Band, Standing } from "../../api/prospectsAndEvidence";
import { Chip } from "../../components/Chip";
import { enumLabel } from "../../shell/format";

/**
 * FR-111: a band is a chip with an icon and its label; a standing other than Ranked is a neutral
 * chip with its label and no band.
 */
export function BandChip({ standing, band }: { standing: Standing; band: Band | null }) {
  if (standing !== "RANKED" || band === null) {
    return <Chip>{enumLabel(standing)}</Chip>;
  }
  const label = enumLabel(band);
  switch (band) {
    case "HOT":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-hint font-medium text-on-accent">
          <FlameIcon size={16} aria-hidden />
          {label}
        </span>
      );
    case "WARM":
      return (
        <Chip tone="accent">
          <SunIcon size={16} aria-hidden />
          {label}
        </Chip>
      );
    case "COLD":
      return (
        <Chip tone="cool">
          <SnowflakeIcon size={16} aria-hidden />
          {label}
        </Chip>
      );
  }
}
