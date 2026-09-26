import { Chip } from "../Chip";
import { ConfidenceWord } from "../../shell/ConfidenceWord";
import { enumLabel, strengthLabel } from "../../shell/format";
import type { Schemas } from "../../api/contract";

/** `FR-115`: Weak, Clear or Strong, a confidence word ([FR-009](
 * /architecture/services/frontend.md#screen-labels)), then the deciding check. */
export function StrengthChip({
  strength,
  confidence,
  decidedBy,
}: {
  strength: Schemas["FindingStrength"];
  confidence: number;
  decidedBy: Schemas["FindingDecidedBy"];
}) {
  return (
    <Chip tone="neutral">
      <span>{strengthLabel(strength)}</span>
      <ConfidenceWord value={confidence} />
      <span>{enumLabel(decidedBy)}</span>
    </Chip>
  );
}
