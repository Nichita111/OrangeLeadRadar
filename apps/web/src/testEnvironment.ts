let reduced = false;

/** Sets what `prefers-reduced-motion` reports in jsdom, which has no `matchMedia`. */
export function setReducedMotion(value: boolean): void {
  reduced = value;
}

export function installMatchMedia(): void {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: query.includes("prefers-reduced-motion") && reduced,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
}

/** jsdom lacks the pointer-capture and scroll APIs Radix calls; these do nothing, as no pointer moves. */
export function installPointerStubs(): void {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => undefined;
  Element.prototype.releasePointerCapture = () => undefined;
  Element.prototype.scrollIntoView = () => undefined;
}

/** jsdom has no canvas; a `null` context is what a browser without WebGL answers, so Aurora falls back. */
export function installCanvasStub(): void {
  HTMLCanvasElement.prototype.getContext = () => null;
}
