import type { ReactElement } from "react";

import { Tooltip } from "../ui/tooltip";
import { useConfig } from "../../shell/config";
import { confidenceWord } from "../../shell/labels";

/** `FR-009`: the word is visible; the contract's numeric confidence appears only on hover. */
export function Confidence({ value }: { value: number }): ReactElement {
  const config = useConfig();
  return (
    <Tooltip label={String(value)}>
      <span>{confidenceWord(value, config.CONFIDENCE_HIGH_MIN, config.CONFIDENCE_MEDIUM_MIN)}</span>
    </Tooltip>
  );
}
