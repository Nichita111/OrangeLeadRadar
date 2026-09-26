import { useEffect } from "react";
import { Outlet, useMatches } from "react-router";

import { isRouteHandle } from "./routeHandle";

/** `document.title` is `<Screen> · LeadRadar`; the deepest route with a title names the screen. */
export function DocumentTitle() {
  const handles = useMatches().flatMap((match) =>
    isRouteHandle(match.handle) ? [match.handle] : [],
  );
  const title = handles.at(-1)?.title;
  useEffect(() => {
    document.title = title === undefined ? "LeadRadar" : `${title} · LeadRadar`;
  }, [title]);
  return <Outlet />;
}
