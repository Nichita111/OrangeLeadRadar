import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, adminPassword } from "../support/env";
import { signInViaUi } from "../support/auth";

// FR-175 (docs/features/identity-and-access.md#users): "Below the users, Pending invites shall
// list email, role, invited by and expiry, each with Revoke, which confirms that the link will
// stop working."

test("AC-78 Users lists a pending invite and Revoke confirms and removes it", async ({ page }) => {
  await signInViaUi(page, ADMIN_EMAIL, adminPassword());
  await page.waitForURL("**/prospects");
  await page.goto("/users");

  const inviteEmail = `ac78-pending-e2e-${Date.now()}@leadradar.local`;
  await page.getByRole("button", { name: "Invite user" }).click();
  await page.getByLabel("Email", { exact: false }).fill(inviteEmail);
  await page.getByLabel("Role", { exact: false }).selectOption("SALES");
  await page.getByRole("button", { name: "Create invite link" }).click();
  await page.getByRole("button", { name: "Done" }).click();

  await expect(page.getByRole("heading", { name: "Pending invites" })).toBeVisible();
  const row = page.locator("tbody tr", { hasText: inviteEmail });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Sales")).toBeVisible();
  await expect(row.getByText("admin")).toBeVisible(); // invited by
  await expect(row.getByRole("button", { name: "Revoke" })).toBeVisible();

  await row.getByRole("button", { name: "Revoke" }).click();
  await expect(
    page.getByText(`The link sent to ${inviteEmail} will stop working at once`, { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Revoke invite" }).click();

  await expect(page.locator("tbody tr", { hasText: inviteEmail })).toHaveCount(0);
});
