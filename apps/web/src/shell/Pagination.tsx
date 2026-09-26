import type { ReactElement } from "react";

import { Button } from "../components/ui/button";

/** `FR-014`: a pager reading `page`, `page_size` and `total` from the answer. */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}): ReactElement {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <nav aria-label="Pagination" className="flex items-center gap-3">
      <Button
        variant="secondary"
        disabled={page <= 1}
        onClick={() => {
          onPageChange(page - 1);
        }}
      >
        Previous
      </Button>
      <span className="text-sm text-text-secondary">
        Page {page} of {pageCount}
      </span>
      <Button
        variant="secondary"
        disabled={page >= pageCount}
        onClick={() => {
          onPageChange(page + 1);
        }}
      >
        Next
      </Button>
    </nav>
  );
}
