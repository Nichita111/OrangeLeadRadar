import { Tooltip } from "../components/Tooltip";
import { useConfig } from "../configContext";
import { confidenceLabel } from "./confidence";
import { useCurrentUser } from "./CurrentUser";

/** FR-009 (amended, N-10): a confidence as a word; the number in a tooltip to an Admin only,
 * never to Sales, on a trigger that also opens on keyboard focus. */
export function ConfidenceWord({ value }: { value: number }) {
  const config = useConfig();
  const user = useCurrentUser();
  const label = confidenceLabel(value, config);
  if (user.role !== "ADMIN") {
    return <span>{label}</span>;
  }
  return (
    <Tooltip content={value.toFixed(2)}>
      <button
        type="button"
        className="cursor-default border-0 bg-transparent p-0 font-inherit text-inherit"
      >
        {label}
      </button>
    </Tooltip>
  );
}
