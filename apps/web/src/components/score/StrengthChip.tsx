import type { components } from "../../api/schema.gen";
import { decidedByLabel, strengthLabel } from "../../shell/labels";

export function StrengthChip({
  strength,
  decidedBy,
}: {
  strength: components["schemas"]["FindingStrength"];
  decidedBy: components["schemas"]["FindingDecidedBy"];
}) {
  return (
    <span className="inline-flex gap-2 rounded-full bg-cool-soft px-2 py-1 text-cool">
      <span>{strengthLabel(strength)}</span>
      <span>{decidedByLabel(decidedBy)}</span>
    </span>
  );
}
