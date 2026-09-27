// `vitest-axe`'s own `extend-expect` module augmentation ships empty in this version; the
// matchers are registered at runtime in `setupTests.ts`, and this declares the one matcher's type.
import type { NoViolationsMatcherResult } from "vitest-axe/matchers";

declare module "vitest" {
  interface Assertion<T = unknown> {
    toHaveNoViolations(this: Assertion<T>): NoViolationsMatcherResult;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): NoViolationsMatcherResult;
  }
}
