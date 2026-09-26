import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  const list = window.matchMedia(QUERY);
  list.addEventListener("change", onChange);
  return () => {
    list.removeEventListener("change", onChange);
  };
}

function snapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

/** True while the user asks for reduced motion (FR-125). */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, snapshot);
}
