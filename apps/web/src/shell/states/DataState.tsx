import type { ReactElement, ReactNode } from "react";
import { ApiError } from "../../api/errors";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingRows } from "./LoadingRows";
import { UnavailableState } from "./UnavailableState";

export function DataState({
  loading,
  error,
  empty,
  emptyHeadline,
  emptySentence,
  emptyAction,
  onEmptyAction,
  retry,
  children,
}: {
  loading: boolean;
  error: unknown;
  empty: boolean;
  emptyHeadline: string;
  emptySentence: string;
  emptyAction: string;
  onEmptyAction: () => void;
  retry: () => void;
  children: ReactNode;
}): ReactElement {
  if (loading) return <LoadingRows />;
  if (
    error instanceof ApiError &&
    (error.status === 503 || (error.status === 429 && error.code === "BUDGET_EXHAUSTED"))
  )
    return <UnavailableState error={error} />;
  if (error instanceof Error) return <ErrorState message={error.message} retry={retry} />;
  if (empty)
    return (
      <EmptyState
        headline={emptyHeadline}
        sentence={emptySentence}
        action={emptyAction}
        onAction={onEmptyAction}
      />
    );
  return <>{children}</>;
}
