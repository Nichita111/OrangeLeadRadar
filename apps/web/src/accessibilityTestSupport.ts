import { axe } from "vitest-axe";
import type userEvent from "@testing-library/user-event";
import { expect } from "vitest";

/** `N-10`, `FR-016`: no serious or critical axe-core violation ([End-to-end tests]
 * (/guidelines/testing.md#end-to-end-tests), [Toolchain](/guidelines/typescript.md#toolchain));
 * jsdom cannot check colour contrast, so that part of `FR-016` rests on QA's Playwright scan
 * against the composed stack. */
export async function expectNoSeriousOrCriticalViolations(container: Element): Promise<void> {
  const results = await axe(container);
  const blocking = results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );
  expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
}

/** `FR-016`: tabs from the top of the document until focus leaves `container` or cycles back to
 * its first stop, returning every element `Tab` visited, in order. Each stop must match
 * `:focus-visible` — the state the app's one, global focus-ring rule
 * ([Accessibility](/architecture/services/frontend.md#accessibility)) keys off, since no
 * component here overrides `outline` — so a stop that only became `document.activeElement`
 * without it (for example, focus assigned by script rather than by the key) fails the walk. */
export async function tabOrderWithin(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
): Promise<HTMLElement[]> {
  const visited: HTMLElement[] = [];
  document.body.focus();
  for (let step = 0; step < 200; step += 1) {
    await user.tab();
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !container.contains(active)) {
      break;
    }
    if (visited.includes(active)) {
      break;
    }
    expect(active.matches(":focus-visible")).toBe(true);
    visited.push(active);
  }
  return visited;
}

/** The enabled buttons, links and form controls of `container` a keyboard user can currently act
 * on, in DOM order — a screen that conditionally renders (tabs, drawers) never leaves an
 * inactive one in the DOM, so this is exactly what one Tab walk must cover. */
const ACTIONABLE_SELECTOR = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[role="button"]:not([aria-disabled="true"])',
].join(", ");

function actionableElements(container: HTMLElement): HTMLElement[] {
  // Every enabled, actionable element is expected to be in the Tab walk, including one given a
  // negative `tabindex` — such an element is unreachable by keyboard, so it must make the walk
  // fail rather than be dropped from what the walk is compared against (A-9).
  return Array.from(container.querySelectorAll<HTMLElement>(ACTIONABLE_SELECTOR));
}

/** `FR-016`: asserts a `tabOrderWithin` walk reached every one of `container`'s enabled buttons,
 * links and form controls, in DOM order — not just some of them, which `visited.length > 0`
 * alone cannot tell apart from a screen where nine actions are unreachable and one is. */
export function expectFullKeyboardCoverage(container: HTMLElement, visited: HTMLElement[]): void {
  expect(visited).toEqual(actionableElements(container));
}

/** `N-10`, `FR-008`, `FR-009`: words and values Sales must never see. */
const SALES_FORBIDDEN_PATTERN = /\bescalation\b|\btriage\b/i;
const PROBABILITY_PATTERN = /\b0\.\d{2}\b/;

export function expectNoSalesForbiddenWording(container: Element): void {
  const text = container.textContent;
  expect(text).not.toMatch(SALES_FORBIDDEN_PATTERN);
  expect(text).not.toMatch(PROBABILITY_PATTERN);
}
