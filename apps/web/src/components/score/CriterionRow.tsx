import {
  CheckIcon,
  CircleDashedIcon,
  CurrencyEurIcon,
  FactoryIcon,
  GlobeHemisphereWestIcon,
  TreeStructureIcon,
  UsersThreeIcon,
  XIcon,
} from "@phosphor-icons/react";

import { enumLabel } from "../../shell/format";
import type { Schemas } from "../../api/contract";

type Criterion = Schemas["FitCriterionBreakdown"];

/** Criterion kind table ([frontend Score presentation](
 * /architecture/services/frontend.md#score-presentation)): the icon and the fact an unknown
 * criterion names. */
const facts: Record<Criterion["kind"], string> = {
  INDUSTRY: "the industry",
  GEOGRAPHY: "the country",
  EMPLOYEE_RANGE: "the employee count",
  REVENUE_RANGE: "the revenue",
  OPERATIONAL_COMPLEXITY: "the operational complexity",
};
const icons = {
  INDUSTRY: FactoryIcon,
  GEOGRAPHY: GlobeHemisphereWestIcon,
  EMPLOYEE_RANGE: UsersThreeIcon,
  REVENUE_RANGE: CurrencyEurIcon,
  OPERATIONAL_COMPLEXITY: TreeStructureIcon,
} satisfies Record<Criterion["kind"], typeof FactoryIcon>;
const marks = { MATCH: CheckIcon, UNKNOWN: CircleDashedIcon, MISMATCH: XIcon } satisfies Record<
  Criterion["match"],
  typeof CheckIcon
>;

/** `FR-114`: a match mark, the criterion's icon, its value, weight level and points; an unknown
 * criterion names the fact that would sharpen the score. */
export function CriterionRow({ criterion }: { criterion: Criterion }) {
  const Icon = icons[criterion.kind];
  const Mark = marks[criterion.match];
  return (
    <div className="flex items-center gap-2">
      <Mark aria-label={criterion.match.toLowerCase()} weight="fill" />
      <Icon aria-hidden />
      <span>{criterion.attribute ?? `Add ${facts[criterion.kind]} to sharpen this score`}</span>
      <span>{enumLabel(criterion.weight)}</span>
      <span className="ml-auto font-mono tabular-nums">
        {criterion.points >= 0 ? "+" : ""}
        {criterion.points}
      </span>
    </div>
  );
}
