import { Link } from "react-router";

export type ServiceTab = "overview" | "questions" | "scoring";

const TABS: { key: ServiceTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "questions", label: "Signal questions" },
  { key: "scoring", label: "Scoring" },
];

function tabRoute(serviceId: string, tab: ServiceTab): string {
  if (tab === "scoring") {
    return `/services/${serviceId}/scoring`;
  }
  return tab === "questions"
    ? `/services/${serviceId}?tab=questions`
    : `/services/${serviceId}`;
}

/**
 * The Service editor's and Scoring settings' shared tab bar (`FR-021` to `FR-037` intro):
 * Overview and Signal questions keep the selected tab in the URL query `tab` (G2); Scoring is a
 * link to the separate route.
 */
export function ServiceTabs({ serviceId, active }: { serviceId: string; active: ServiceTab }) {
  return (
    <div role="tablist" aria-label="Service" className="flex gap-2 border-b border-border">
      {TABS.map((tab) => (
        <Link
          key={tab.key}
          to={tabRoute(serviceId, tab.key)}
          role="tab"
          aria-selected={tab.key === active}
          className={
            tab.key === active
              ? "border-b-2 border-accent px-3 py-2 font-medium text-text no-underline"
              : "px-3 py-2 font-medium text-text-secondary no-underline hover:text-text"
          }
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
