import { PageNotice } from "./PageNotice";

/** FR-159: a route that matches no screen. */
export function NotFound() {
  return (
    <PageNotice
      title="Page not found"
      lead="This page does not exist."
      linkLabel="Go to Prospects"
    />
  );
}
