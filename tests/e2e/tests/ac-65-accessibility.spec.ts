/**
 * AC-65 (docs/requirements/acceptance.md, N-10):
 *
 * "Given every screen, when an automated accessibility scan runs as a Sales user and as an
 * Admin, then it reports no serious or critical violation, every action is reachable by
 * keyboard, and no screen available to Sales shows a raw probability or the words
 * "escalation" or "triage"."
 *
 * Scope (task.md, `refresh-degradation-retention`): "in scope for the built screens only;
 * unbuilt screens are deferred to their frontend tasks." Routes come from
 * docs/architecture/services/frontend.md#routes. Anonymous screens (Landing, Sign in) are
 * scanned once, unauthenticated; every other route is scanned as Sales when its Roles column
 * is "any", and as both Sales and Admin only where Admin is listed — a route whose Roles
 * column is "Admin" is not "available to Sales" (docs/architecture/interfaces.md#conventions,
 * role symbol `A`), so it is scanned as Admin alone.
 *
 * The scan is `@axe-core/playwright` (docs/guidelines/testing.md#end-to-end-tests, task
 * decision G8); a violation of impact "serious" or "critical" fails the test.
 *
 * A route that a build has not reached yet (the SPA renders no screen content for it) is
 * reported NOT RUN for that route rather than failed, per task.md's "built screens only"
 * scope; the qa-report.md lists which routes that applied to.
 */
import { test, expect, Page, APIRequestContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { signIn, Role } from "../support/auth";

interface RouteSpec {
  path: string;
  screen: string;
  roles: "any" | "admin";
  needsAccountId?: boolean;
  needsServiceId?: boolean;
}

// docs/architecture/services/frontend.md#routes, excluding `/` and `/login` (handled below).
const ROUTES: RouteSpec[] = [
  { path: "/prospects", screen: "Prospects", roles: "any" },
  { path: "/accounts/:id", screen: "Account detail", roles: "any", needsAccountId: true },
  { path: "/alerts", screen: "Alerts", roles: "any" },
  { path: "/accounts", screen: "Accounts", roles: "any" },
  { path: "/accounts/:id/profile", screen: "Account profile", roles: "any", needsAccountId: true },
  { path: "/accounts/import", screen: "Account import", roles: "any" },
  { path: "/suggested-accounts", screen: "Suggested accounts", roles: "any" },
  { path: "/runs", screen: "Runs", roles: "any" },
  { path: "/labelling", screen: "Labelling", roles: "any" },
  { path: "/accounts/:id/outreach", screen: "Outreach composer", roles: "any", needsAccountId: true },
  { path: "/services", screen: "Services", roles: "admin" },
  { path: "/services/:id", screen: "Service editor", roles: "admin", needsServiceId: true },
  { path: "/services/:id/scoring", screen: "Scoring settings", roles: "admin", needsServiceId: true },
  { path: "/settings/industries-markets", screen: "Industries and markets", roles: "admin" },
  { path: "/quality", screen: "Quality report", roles: "admin" },
  { path: "/settings/source-plugins", screen: "Source plug-ins", roles: "admin" },
  { path: "/users", screen: "Users", roles: "admin" },
  { path: "/audit", screen: "Audit log", roles: "admin" },
];

// FR-008 (docs/architecture/services/frontend.md#screen-labels) allows "escalation", "triage"
// and raw probabilities on the Admin screens Quality report and Audit log, and in the
// Admin-only details of Runs — none of those are "available to Sales", so AC-65's word ban
// applies to every route scanned as Sales here without exception.
const FORBIDDEN_WORDS = [/\bescalation\b/i, /\btriage\b/i];
// A bare decimal between 0 and 1 with two or three places, the shape of a raw p_positive or
// confidence number (docs/architecture/services/frontend.md FR-009: "to Sales never").
const RAW_PROBABILITY = /\b0\.\d{2,3}\b/;

async function resolveIds(request: APIRequestContext): Promise<{ accountId: string | null; serviceId: string | null }> {
  const accountsResp = await request.get("/api/v1/accounts", { params: { page_size: "1" } });
  const servicesResp = await request.get("/api/v1/services");
  const accountId = accountsResp.ok() ? (await accountsResp.json()).items?.[0]?.id ?? null : null;
  const services = servicesResp.ok() ? await servicesResp.json() : [];
  const serviceId = Array.isArray(services) && services.length > 0 ? services[0].id : null;
  return { accountId, serviceId };
}

/**
 * Black-box "is this screen built" check: a route the SPA has not implemented yet renders no
 * heading, no landmark and no substantial text — this suite never reads the frontend source
 * to decide, only what the browser shows.
 */
async function screenIsBuilt(page: Page): Promise<boolean> {
  // The SPA may still be fetching its data (TanStack Query) right after navigation, so this
  // gives it a real chance to render before concluding the route has no screen: wait for the
  // network to settle, then for a heading or a main landmark to appear.
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
  const appeared = await page
    .locator("main, [role=main], h1, h2, [role=heading]")
    .first()
    .waitFor({ state: "visible", timeout: 10_000 })
    .then(() => true)
    .catch(() => false);
  if (!appeared) return false;
  const bodyText = (await page.locator("body").innerText().catch(() => "")).trim();
  return bodyText.length > 40;
}

async function runAxeScan(page: Page, label: string) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious, `${label}: serious/critical axe violations:\n${JSON.stringify(serious, null, 2)}`).toEqual([]);
}

const ACTIONABLE_SELECTOR =
  'a[href], button:not([disabled]), [role="button"]:not([aria-disabled="true"]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [role="link"], [role="menuitem"], [role="tab"]';

async function assertKeyboardReachable(page: Page, label: string) {
  // Every actionable control (link, button, textbox, combobox, checkbox, radio, menuitem)
  // shall be reachable by keyboard (FR-016). This walks the keyboard itself — pressing Tab
  // repeatedly from the top of the document — rather than only inspecting `tabindex`, so a
  // control skipped by a broken tab order, a focus trap or an invisible element stealing focus
  // makes the test fail, not merely one carrying a literal `tabindex="-1"`.
  const taggedCount = await page.evaluate((selector) => {
    const nodes = Array.from(document.querySelectorAll(selector));
    let n = 0;
    for (const el of nodes) {
      el.removeAttribute("data-ac65-idx");
      const rects = el.getClientRects();
      const style = window.getComputedStyle(el);
      const visible = rects.length > 0 && style.visibility !== "hidden" && style.display !== "none";
      if (visible) {
        el.setAttribute("data-ac65-idx", String(n));
        n += 1;
      }
    }
    return n;
  }, ACTIONABLE_SELECTOR);

  if (taggedCount === 0) return;

  await page.evaluate(() => {
    (document.activeElement as HTMLElement | null)?.blur?.();
    document.body.focus();
  });

  const reached = new Set<number>();
  const maxPresses = taggedCount * 4 + 30;
  let previousIdx: number | null = null;
  let stableRepeats = 0;
  for (let i = 0; i < maxPresses && reached.size < taggedCount; i++) {
    await page.keyboard.press("Tab");
    const idx: number | null = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      const attr = el?.getAttribute("data-ac65-idx");
      return attr === null || attr === undefined ? null : Number(attr);
    });
    if (idx !== null) reached.add(idx);
    if (idx === previousIdx) {
      stableRepeats += 1;
      if (stableRepeats > 3) break; // focus stopped moving — stop probing instead of spinning
    } else {
      stableRepeats = 0;
    }
    previousIdx = idx;
  }

  const untabbable: string[] = [];
  if (reached.size < taggedCount) {
    const missing = await page.evaluate((selector) => {
      const nodes = Array.from(document.querySelectorAll(selector));
      const out: string[] = [];
      for (const el of nodes) {
        const attr = el.getAttribute("data-ac65-idx");
        if (attr === null) continue;
        out.push(`${el.tagName}#${attr} "${el.getAttribute("aria-label") || (el as HTMLElement).innerText || el.getAttribute("name") || ""}"`);
      }
      return out;
    }, ACTIONABLE_SELECTOR);
    for (let idx = 0; idx < taggedCount; idx++) {
      if (!reached.has(idx)) untabbable.push(missing[idx] ?? `#${idx}`);
    }
  }

  await page.evaluate((selector) => {
    document.querySelectorAll(selector).forEach((el) => el.removeAttribute("data-ac65-idx"));
  }, ACTIONABLE_SELECTOR);

  expect(
    untabbable,
    `${label}: actionable elements never reached by pressing Tab from the top of the document (${reached.size}/${taggedCount} reached): ${untabbable.join(", ")}`,
  ).toEqual([]);
}

async function assertNoForbiddenWordsForSales(page: Page, label: string) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN_WORDS) {
    expect(pattern.test(text), `${label}: Sales screen shows the forbidden word ${pattern}`).toBeFalsy();
  }
  expect(RAW_PROBABILITY.test(text), `${label}: Sales screen shows a raw probability-looking number (${RAW_PROBABILITY})`).toBeFalsy();
}

function fillPath(route: RouteSpec, ids: { accountId: string | null; serviceId: string | null }): string | null {
  let path = route.path;
  if (route.needsAccountId) {
    if (!ids.accountId) return null;
    path = path.replace(":id", ids.accountId);
  }
  if (route.needsServiceId) {
    if (!ids.serviceId) return null;
    path = path.replace(":id", ids.serviceId);
  }
  return path;
}

test.describe("AC-65 accessibility scan", () => {
  test("AC-65 Landing (anonymous) has no serious or critical violation and is keyboard reachable", async ({ page }) => {
    await page.goto("/");
    if (!(await screenIsBuilt(page))) {
      test.skip(true, "NOT RUN: Landing (/) renders no heading/landmark content — not built yet.");
    }
    await runAxeScan(page, "Landing (/)");
    await assertKeyboardReachable(page, "Landing (/)");
  });

  test("AC-65 Sign in (anonymous) has no serious or critical violation and is keyboard reachable", async ({ page }) => {
    await page.goto("/login");
    if (!(await screenIsBuilt(page))) {
      test.skip(true, "NOT RUN: Sign in (/login) renders no heading/landmark content — not built yet.");
    }
    await runAxeScan(page, "Sign in (/login)");
    await assertKeyboardReachable(page, "Sign in (/login)");
  });

  for (const route of ROUTES) {
    const roles: Role[] = route.roles === "admin" ? ["ADMIN"] : ["SALES", "ADMIN"];
    for (const role of roles) {
      test(`AC-65 ${route.screen} (${route.path}) as ${role}: no serious/critical violation, keyboard reachable${role === "SALES" ? ", no raw probability or escalation/triage wording" : ""}`, async ({ page, request }) => {
        await signIn(page, role);
        const ids = await resolveIds(page.context().request);
        const path = fillPath(route, ids);
        if (path === null) {
          test.skip(true, `NOT RUN: no seeded ${route.needsAccountId ? "account" : "service"} id available to build ${route.path} — the demo dataset must be seeded first.`);
        }
        await page.goto(path as string);
        if (!(await screenIsBuilt(page))) {
          test.skip(true, `NOT RUN: ${route.screen} (${path}) renders no heading/landmark content as ${role} — not built yet (task.md: "in scope for the built screens only").`);
        }
        const label = `${route.screen} (${path}) as ${role}`;
        await runAxeScan(page, label);
        await assertKeyboardReachable(page, label);
        if (role === "SALES") {
          await assertNoForbiddenWordsForSales(page, label);
        }
      });
    }
  }
});
