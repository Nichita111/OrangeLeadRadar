import { useCallback, useEffect, useMemo, useState } from "react";

import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

type AuroraModule = typeof import("./AuroraCanvas");

interface AuroraProps {
  /** Loads the WebGL chunk; the only place a WebGL library is imported (FR-128). */
  load?: () => Promise<AuroraModule>;
}

function readToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

const loadCanvas = () => import("./AuroraCanvas");

/**
 * The Aurora background of Sign in (FR-124, FR-125, FR-128): a still gradient of the Accent and
 * Accent soft colours that stays under the animated canvas, and stays alone under reduced motion
 * or when the chunk or WebGL fails to load.
 */
export function Aurora({ load = loadCanvas }: AuroraProps) {
  const reduced = usePrefersReducedMotion();
  const [loaded, setLoaded] = useState<AuroraModule | null>(null);
  const [failed, setFailed] = useState(false);
  const onError = useCallback(() => {
    setFailed(true);
  }, []);

  useEffect(() => {
    if (reduced) {
      return undefined;
    }
    let cancelled = false;
    load().then(
      (module) => {
        if (!cancelled) {
          setLoaded(module);
        }
      },
      () => {
        // The still gradient is the specified state when the background cannot load (FR-128).
        if (!cancelled) {
          setFailed(true);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [reduced, load]);

  const showCanvas = !reduced && !failed && loaded !== null;
  // The tokens are read once per mount, so a re-render never rebuilds the WebGL context.
  const { colorStops, surface, lightMode } = useMemo(
    () => ({
      colorStops: [readToken("--accent"), readToken("--accent-soft"), readToken("--accent")],
      surface: readToken("--surface"),
      lightMode: !window.matchMedia("(prefers-color-scheme: dark)").matches,
    }),
    [],
  );

  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      <div
        data-testid="aurora-still"
        className="absolute inset-0 bg-linear-to-br from-accent-soft via-accent-soft to-accent opacity-60"
      />
      {showCanvas && (
        <div className="absolute inset-0 opacity-60">
          <loaded.AuroraCanvas
            colorStops={colorStops}
            surface={surface}
            lightMode={lightMode}
            onError={onError}
          />
        </div>
      )}
    </div>
  );
}
