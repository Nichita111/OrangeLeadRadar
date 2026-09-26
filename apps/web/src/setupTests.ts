import "@testing-library/jest-dom/vitest";

HTMLElement.prototype.setPointerCapture = () => undefined;
HTMLElement.prototype.releasePointerCapture = () => undefined;

// jsdom implements neither: Radix's popper (Tooltip, Select) and sonner's toasts both measure
// their content with a `ResizeObserver`.
class NoopResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = NoopResizeObserver;
