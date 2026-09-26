/** What a route says about itself to the shell: its screen title for the header and the tab. */
export interface RouteHandle {
  title: string;
  adminOnly?: true;
}

export function isRouteHandle(value: unknown): value is RouteHandle {
  return (
    typeof value === "object" &&
    value !== null &&
    "title" in value &&
    typeof value.title === "string"
  );
}
