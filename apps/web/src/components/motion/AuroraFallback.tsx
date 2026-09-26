/**
 * The still gradient of [`AuroraBackground`](./AuroraBackground.tsx): its
 * `prefers-reduced-motion` state (`FR-125`), its `Suspense` fallback while the lazy chunk loads,
 * and what stays on screen if that chunk fails to load (`FR-128`) — the same colours, without
 * the entrance transform.
 */
const AURORA_GRADIENT =
  "radial-gradient(circle at 15% 20%, var(--color-accent-soft), transparent 55%), " +
  "radial-gradient(circle at 85% 25%, var(--color-cool-soft), transparent 50%), " +
  "radial-gradient(circle at 50% 95%, var(--color-accent), transparent 45%)";

export function AuroraFallback() {
  return (
    <div aria-hidden="true" className="absolute inset-0" style={{ background: AURORA_GRADIENT }} />
  );
}

export { AURORA_GRADIENT };
