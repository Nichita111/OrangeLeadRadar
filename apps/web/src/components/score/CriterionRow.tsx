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
import type { components } from "../../api/schema.gen";

type Criterion = components["schemas"]["FitCriterionBreakdown"];
const facts: Record<Criterion["kind"], string> = {
  INDUSTRY: "industry",
  GEOGRAPHY: "country",
  EMPLOYEE_RANGE: "employee count",
  REVENUE_RANGE: "revenue",
  OPERATIONAL_COMPLEXITY: "operational complexity",
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

export function CriterionRow({ criterion }: { criterion: Criterion }) {
  const Icon = icons[criterion.kind];
  const Mark = marks[criterion.match];
  return (
    <div className="flex items-center gap-2">
      <Mark aria-label={criterion.match.toLowerCase()} />
      <Icon aria-hidden />
      <span>{criterion.attribute ?? `Add the ${facts[criterion.kind]} to sharpen this score`}</span>
      <span>{criterion.weight.toLowerCase()}</span>
      <span className="ml-auto font-mono">
        {criterion.points >= 0 ? "+" : ""}
        {criterion.points}
      </span>
    </div>
  );
}
