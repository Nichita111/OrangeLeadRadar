import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, adminPassword } from "../support/env";
import { loseAndRegainFocus, signInViaUi } from "../support/auth";

// task.md, "Reported defect": "whenever I alt tab, it resets" - expected behaviour, decided by
// the owner: "switching to another window and back leaves the screen as it was - what the user
// typed, the step or scroll position they were on, and any dialog they had open stay unchanged."
// Covered here on Accept invite (fields typed, password column), Users (Invite user dialog open,
// link shown), Sign in (fields typed) and Landing (scroll position and current step), by
// dispatching `blur`/`focus` on the window and `visibilitychange` and asserting nothing reset.

test("Reported defect: Sign in keeps typed fields across a lost and regained focus", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: false }).fill("still-typing@leadradar.local");
  await page.getByLabel("Password", { exact: false }).fill("not-yet-submitted");

  await loseAndRegainFocus(page);

  await expect(page.getByLabel("Email", { exact: false })).toHaveValue("still-typing@leadradar.local");
  await expect(page.getByLabel("Password", { exact: false })).toHaveValue("not-yet-submitted");
});

test("Reported defect: Accept invite keeps the typed fields and the password column across a lost and regained focus", async ({
  browser,
}) => {
  const adminPage = await browser.newPage();
  await signInViaUi(adminPage, ADMIN_EMAIL, adminPassword());
  await adminPage.waitForURL("**/prospects");

  const inviteEmail = `defect-accept-${Date.now()}@leadradar.local`;
  const created = await adminPage.request.post("/api/v1/invites", {
    headers: { "X-Requested-With": "XMLHttpRequest" },
    data: { email: inviteEmail, role: "SALES" },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const { link } = await created.json();
  const token = (link as string).split("#", 2)[1];

  const page = await browser.newPage();
  await page.goto(`/invite#${token}`);
  await page.getByLabel("Display name", { exact: false }).fill("Still Typing");
  await page.getByLabel("Password", { exact: false }).fill("half-typed-pw");
  const columnBefore = await page.locator(".ai-col-count").textContent();

  await loseAndRegainFocus(page);

  await expect(page.getByLabel("Display name", { exact: false })).toHaveValue("Still Typing");
  await expect(page.getByLabel("Password", { exact: false })).toHaveValue("half-typed-pw");
  await expect(page.locator(".ai-col-count")).toHaveText(columnBefore ?? "");
});

test("Reported defect: Users keeps the Invite user dialog and the shown link across a lost and regained focus", async ({
  page,
}) => {
  await signInViaUi(page, ADMIN_EMAIL, adminPassword());
  await page.waitForURL("**/prospects");
  await page.goto("/users");

  await page.getByRole("button", { name: "Invite user" }).click();
  const inviteEmail = `defect-users-${Date.now()}@leadradar.local`;
  await page.getByLabel("Email", { exact: false }).fill(inviteEmail);

  await loseAndRegainFocus(page);

  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Email", { exact: false })).toHaveValue(inviteEmail);

  await page.getByRole("button", { name: "Create invite link" }).click();
  const linkInput = page.getByLabel(`Invite link for ${inviteEmail}`);
  await expect(linkInput).toBeVisible();
  const linkBefore = await linkInput.inputValue();

  await loseAndRegainFocus(page);

  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel(`Invite link for ${inviteEmail}`)).toHaveValue(linkBefore);
});

test("Reported defect: Landing keeps its scroll position and current step across a lost and regained focus", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sift", exact: true }).click();
  await page.waitForTimeout(500); // FR-161's scroll-to-step animation settling

  const scrollBefore = await page.evaluate(() => window.scrollY);
  const currentStepBefore = await page.getByRole("button", { name: "Sift", exact: true }).getAttribute("aria-current");
  expect(currentStepBefore).toBe("step");

  await loseAndRegainFocus(page);

  const scrollAfter = await page.evaluate(() => window.scrollY);
  const currentStepAfter = await page.getByRole("button", { name: "Sift", exact: true }).getAttribute("aria-current");

  expect(scrollAfter).toBe(scrollBefore);
  expect(currentStepAfter).toBe("step");
});
