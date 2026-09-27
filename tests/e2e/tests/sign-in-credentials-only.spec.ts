import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, SALES_EMAIL, adminPassword, salesPassword } from "../support/env";
import { signInViaUi } from "../support/auth";

// docs/features/identity-and-access.md#sign-in, "which now offers only email and password"
// (task.md): `S-SEC-04` and the demo sign-in (`AC-76`, `AC-77`) are retired.

test("Sign in offers only email and password, with no other sign-in shortcut (FR-160)", async ({ page }) => {
  await page.goto("/login");

  // FR-160: "a brand panel carrying the LeadRadar wordmark and the headline ... over the Aurora
  // background ... and a panel with the form; the brand panel carries no other text and no
  // sign-in shortcut."
  await expect(
    page.getByText("Know which accounts to call, and exactly why."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toHaveCount(1);
  await expect(page.getByRole("button")).toHaveCount(1);
  await expect(page.getByRole("link")).toHaveCount(0);

  // FR-152: a hint under each field.
  await expect(page.getByLabel("Email", { exact: false })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: false })).toBeVisible();
});

test("FR-093 correct credentials sign in and go to /prospects; FR-094 wrong credentials show one message", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: false }).fill(SALES_EMAIL);
  await page.getByLabel("Password", { exact: false }).fill("definitely-the-wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  const alertCount = await page.getByRole("alert").count();
  expect(alertCount).toBe(1);

  await signInViaUi(page, SALES_EMAIL, salesPassword());
  await page.waitForURL("**/prospects");
});

test("FR-093 the return path is followed only when it is a path of this client", async ({ browser }) => {
  const validReturn = await browser.newPage();
  await signInViaUi(validReturn, ADMIN_EMAIL, adminPassword(), "/users");
  await validReturn.waitForURL("**/users");

  const externalReturn = await browser.newPage();
  await signInViaUi(externalReturn, ADMIN_EMAIL, adminPassword(), "https://evil.example.com");
  await externalReturn.waitForURL("**/prospects");
  expect(externalReturn.url()).not.toContain("evil.example.com");
});

test("FR-093 a signed-in user who opens Sign in goes to /prospects", async ({ page }) => {
  await signInViaUi(page, SALES_EMAIL, salesPassword());
  await page.waitForURL("**/prospects");
  await page.goto("/login");
  await page.waitForURL("**/prospects");
});
