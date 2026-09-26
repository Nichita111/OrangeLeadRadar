import { expect, test, type Page } from "@playwright/test";

const workEntries = [
  "Prospects",
  "Alerts",
  "Accounts",
  "Suggested accounts",
  "Runs",
  "Labelling",
];
const adminEntries = [
  "Services",
  "Industries and markets",
  "Quality",
  "Source plug-ins",
  "Users",
  "Audit log",
];

async function openShell(page: Page, role: "ADMIN" | "SALES", path = "/prospects") {
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  if (!(await page.evaluate(() => Boolean(navigator.serviceWorker.controller)))) {
    await page.reload();
  }
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
  await page.evaluate(
    async ({ role, path }) => {
      const response = await fetch("/api/v1/auth/demo-login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({ role }),
      });
      if (!response.ok) throw new Error(`demo login setup failed: ${response.status}`);
      history.pushState({}, "", path);
      dispatchEvent(new PopStateEvent("popstate"));
    },
    { role, path },
  );
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

test("FR-006 anonymous protected routes retain the return path", async ({ page }) => {
  await page.goto("/accounts/account-dhl");
  await expect(page).toHaveURL(/\/login\?return=%2Faccounts%2Faccount-dhl$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("FR-001 FR-002 FR-004 FR-101 FR-102 Admin shell exposes the specified navigation and identity", async ({ page }) => {
  await openShell(page, "ADMIN");

  await expect(page.getByText("Work", { exact: true })).toBeVisible();
  await expect(page.getByText("Admin only", { exact: true })).toBeVisible();
  for (const label of [...workEntries, ...adminEntries]) {
    const link = page.getByRole("link", { name: new RegExp(`^${label}`) });
    await expect(link).toBeVisible();
    await expect(link.locator("svg")).toHaveCount(1);
  }
  await expect(page.getByRole("link", { name: /^Alerts/ })).toContainText("3");
  await expect(page.getByRole("link", { name: "Prospects" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("Admin demo", { exact: true })).toBeVisible();
  await expect(page.getByText("Admin", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Prospects");

  await page.evaluate(() => {
    history.pushState({}, "", "/accounts/account-dhl");
    dispatchEvent(new PopStateEvent("popstate"));
  });
  const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(breadcrumb.getByRole("link", { name: "Accounts" })).toHaveAttribute("href", "/accounts");
  await expect(breadcrumb.getByText("Account detail", { exact: true })).toHaveAttribute("aria-current", "page");

  await page.getByRole("link", { name: "Services" }).click();
  await expect(page.getByText("Admin only", { exact: true }).last()).toBeVisible();
});

test("FR-001 FR-003 FR-006 Sales shell is role-gated and remembers its service", async ({ page }) => {
  await openShell(page, "SALES");

  for (const label of workEntries) {
    await expect(page.getByRole("link", { name: new RegExp(`^${label}`) })).toBeVisible();
  }
  for (const label of adminEntries) {
    await expect(page.getByRole("link", { name: label, exact: true })).toHaveCount(0);
  }
  await expect(page.getByText("Admin only", { exact: true })).toHaveCount(0);

  const selector = page.getByRole("combobox", { name: "Service" });
  await expect(selector).toHaveText("Intelligent Automation");
  const initialService = await page.evaluate(() => localStorage.getItem("leadradar:selected-service:user-sales"));
  await selector.click();
  await expect(page.getByRole("option", { name: "Intelligent Automation" })).toBeVisible();
  await page.getByRole("option", { name: "Cybersecurity services" }).click();
  await expect(selector).toHaveText("Cybersecurity services");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("leadradar:selected-service:user-sales"))).not.toBe(initialService);
  await page.getByRole("link", { name: /^Alerts/ }).click();
  await expect(page.getByRole("combobox", { name: "Service" })).toHaveText("Cybersecurity services");

  await page.evaluate(() => {
    history.pushState({}, "", "/services");
    dispatchEvent(new PopStateEvent("popstate"));
  });
  await expect(page.getByRole("heading", { name: "Not allowed" })).toBeVisible();
  await expect(page.getByText("This screen needs the Admin role.")).toBeVisible();
});

test("FR-008 FR-009 FR-010 FR-011 FR-016 FR-017 shell is keyboard-usable, local, and fits 1024 px", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 1024, height: 800 } });
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol.startsWith("http") && url.origin !== "http://127.0.0.1:8080") externalRequests.push(request.url());
  });
  await openShell(page, "SALES");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Prospects" })).toBeFocused();
  const focusStyle = await page.getByRole("link", { name: "Prospects" }).evaluate((element) => {
    const style = getComputedStyle(element);
    return { outlineWidth: style.outlineWidth, outlineStyle: style.outlineStyle };
  });
  expect(focusStyle.outlineStyle).not.toBe("none");
  expect(focusStyle.outlineWidth).not.toBe("0px");

  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBe(dimensions.clientWidth);
  expect(externalRequests).toEqual([]);
  await expect(page.locator("body")).not.toContainText(/p_positive|escalation|triage|token counts/i);
  await page.close();
});
