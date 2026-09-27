import { useEffect } from "react";

/** The LeadRadar mark of the dark pages' headers. */
export function Mark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <circle cx="12" cy="12" r="9.5" className="stroke-text-tertiary" />
      <circle cx="12" cy="12" r="5" className="stroke-text-tertiary" />
      <circle cx="15.6" cy="8.4" r="2.2" className="fill-accent" />
    </svg>
  );
}

/** FR-106: Landing and Accept invite are dark in both schemes, and only while they are shown. */
export function useDarkScheme() {
  useEffect(() => {
    const root = document.documentElement;
    root.dataset["scheme"] = "dark";
    return () => {
      delete root.dataset["scheme"];
    };
  }, []);
}
