import { Tooltip } from "../components/Tooltip";
import { useConfig } from "../configContext";
import { confidenceLabel } from "./confidence";

/** FR-009: a confidence as a word; the number only in a tooltip. */
export function ConfidenceWord({ value }: { value: number }) {
  const config = useConfig();
  return (
    <Tooltip content={value.toFixed(2)}>
      <span>{confidenceLabel(value, config)}</span>
    </Tooltip>
  );
}
