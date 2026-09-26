import type { ReactElement } from "react";
import { BlurInText } from "../../components/motion/BlurInText";
import { Button } from "../../components/ui/button";

export function EmptyState({
  headline,
  sentence,
  action,
  onAction,
}: {
  headline: string;
  sentence: string;
  action: string;
  onAction: () => void;
}): ReactElement {
  return (
    <div className="rounded-card border border-border p-6 text-center">
      <h2 className="text-section-title font-semibold">
        <BlurInText>{headline}</BlurInText>
      </h2>
      <p className="my-3 text-text-secondary">{sentence}</p>
      <Button variant="primary" onClick={onAction}>
        {action}
      </Button>
    </div>
  );
}
