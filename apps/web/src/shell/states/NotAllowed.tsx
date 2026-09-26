import { PageNotice } from "./PageNotice";

/** FR-006: a `403` shows a page naming the role required. */
export function NotAllowed() {
  return (
    <PageNotice
      title="Not allowed"
      lead="This page needs the Admin role."
      linkLabel="Back to Prospects"
    />
  );
}
