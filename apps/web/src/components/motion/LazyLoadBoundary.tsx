/**
 * Catches a failed `React.lazy` chunk load. React offers no hook for this — an error boundary is
 * the one seam the framework itself requires a class for, like the classifier and source-plugin
 * adapters of [coding guidelines](/guidelines/coding.md#functions-first); it holds no other
 * state and does nothing a function component could. Used only by `SignInScreen` for `FR-128`:
 * the lazy `AuroraBackground` failing to load falls back to the same still gradient as its
 * `Suspense` fallback.
 */
import { Component, type ReactNode } from "react";

interface LazyLoadBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

interface LazyLoadBoundaryState {
  failed: boolean;
}

export class LazyLoadBoundary extends Component<LazyLoadBoundaryProps, LazyLoadBoundaryState> {
  state: LazyLoadBoundaryState = { failed: false };

  static getDerivedStateFromError(): LazyLoadBoundaryState {
    return { failed: true };
  }

  render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
