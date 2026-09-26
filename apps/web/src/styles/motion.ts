/**
 * The design values of [Motion](/architecture/services/frontend.md#motion): the one place every
 * timing, easing and spring setting is named, so a component never repeats a literal.
 */

export const MOTION = {
  enterMs: 200,
  exitMs: 150,
  countUpMs: 600,
  staggerMs: 40,
  easing: [0.16, 1, 0.3, 1] as const,
  spring: { stiffness: 100, damping: 20 },
  toastVisibleMs: 6000,
} as const;
