import { CheckIcon } from "@phosphor-icons/react";
import type { ReactElement } from "react";
import { ApiError } from "../../api/errors";
import { BUDGET_EXHAUSTED_STILL_WORKS, dependencyLabel, stillWorksFor } from "./degradation";

function detail(error: ApiError, key: string): string | undefined {
  if (typeof error.details !== "object" || error.details === null) return undefined;
  const value = (error.details as Record<string, unknown>)[key];
  return typeof value === "string" ? value : undefined;
}

export function UnavailableState({ error }: { error: ApiError }): ReactElement {
  const dependency = detail(error, "dependency");
  const budget = error.status === 429 && error.code === "BUDGET_EXHAUSTED";
  const items = budget
    ? BUDGET_EXHAUSTED_STILL_WORKS
    : dependency === undefined
      ? []
      : stillWorksFor(dependency);
  const name = budget
    ? "The LLM daily budget"
    : dependency === undefined
      ? "A dependency"
      : dependencyLabel(dependency);
  return (
    <div role="alert" className="rounded-card border border-caution bg-caution-soft p-4">
      <h2 className="font-semibold">{name} is unavailable</h2>
      <p className="mt-1">{error.message}</p>
      <p className="mt-3 font-semibold">What still works</p>
      <ul>
        {items.map((item) => (
          <li key={item} className="flex items-center gap-2">
            <CheckIcon size={16} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
