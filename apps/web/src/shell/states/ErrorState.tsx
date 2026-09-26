import type { ReactElement } from "react";
import { Button } from "../../components/ui/button";
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}): ReactElement {
  return (
    <div role="alert" className="rounded-card border border-negative p-4">
      <p>{message}</p>
      <Button className="mt-3" onClick={retry}>
        Retry
      </Button>
    </div>
  );
}
