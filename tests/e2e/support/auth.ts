import type { Page } from "@playwright/test";

/** Signs in through Sign in (docs/features/identity-and-access.md#sign-in): email and password
 * only (`FR-093`), optionally with a `return` path. */
export async function signInViaUi(page: Page, email: string, password: string, returnPath?: string) {
  const url = returnPath ? `/login?return=${encodeURIComponent(returnPath)}` : "/login";
  await page.goto(url);
  await page.getByLabel("Email", { exact: false }).fill(email);
  await page.getByLabel("Password", { exact: false }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** Dispatches the events of the reported defect: the window loses and regains focus, and the
 * page's visibility changes and comes back - task.md's "Reported defect": "make the page lose
 * and regain focus (blur/focus on the window and visibilitychange)". `document.visibilityState`
 * is forced to `hidden` and back (a real alt-tab changes it; Playwright's tab never truly loses
 * OS focus) so a handler gated on the actual hidden -> visible transition, not just the event, is
 * exercised too. `visibilitychange` is dispatched with `bubbles: true`: a real browser fires it on
 * `document` as a bubbling event, so it also reaches a listener attached to `window`; a
 * non-bubbling synthetic event would not, and would not reproduce a window switch for such a
 * listener. Waits for the network to go idle afterwards, since a reset may happen during a
 * request the switch triggers (e.g. a refetch on window focus), not only synchronously. */
export async function loseAndRegainFocus(page: Page) {
  await page.evaluate(() => {
    const setVisibility = (state: DocumentVisibilityState) => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
      Object.defineProperty(document, "hidden", { configurable: true, get: () => state === "hidden" });
      document.dispatchEvent(new Event("visibilitychange", { bubbles: true }));
    };
    window.dispatchEvent(new Event("blur"));
    setVisibility("hidden");
    setVisibility("visible");
    window.dispatchEvent(new Event("focus"));
  });
  await page.waitForLoadState("networkidle");
}
