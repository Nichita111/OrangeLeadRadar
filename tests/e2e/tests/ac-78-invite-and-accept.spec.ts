import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, adminPassword } from "../support/env";
import { signInViaUi } from "../support/auth";

// AC-78 (docs/requirements/acceptance.md): "Given an Admin, when they invite
// `new.sales@leadradar.local` as Sales, then `API-79` returns the invite with a link under
// `APP_BASE_URL` carrying the token after `#` ... with that token `API-81` returns the email,
// role, inviter and expiry, and `API-82` with a display name and a password of
// `PASSWORD_MIN_LENGTH` characters answers as `API-01` would ... creates an active Sales user
// ... and opens Prospects."
//
// Journey: Users' Invite user dialog (`FR-174`, docs/features/identity-and-access.md#users) to
// Accept invite (`FR-169` to `FR-173`, docs/features/identity-and-access.md#accept-invite).
// APP_BASE_URL and INVITE_TTL_HOURS default to `http://localhost:8080` and `72`
// (docs/architecture/services/api.md#runtime); the invited address is made unique per run.

test("AC-78 an Admin invites a Sales user from Users and the invitee accepts it on Accept invite", async ({
  browser,
}) => {
  const adminPage = await browser.newPage();
  await signInViaUi(adminPage, ADMIN_EMAIL, adminPassword());
  await adminPage.waitForURL("**/prospects");

  await adminPage.goto("/users");
  await adminPage.getByRole("button", { name: "Invite user" }).click();

  const inviteEmail = `ac78-e2e-${Date.now()}@leadradar.local`;
  await adminPage.getByLabel("Email", { exact: false }).fill(inviteEmail);
  await adminPage.getByLabel("Role", { exact: false }).selectOption("SALES");
  await adminPage.getByRole("button", { name: "Create invite link" }).click();

  // FR-174: "show the link once with a Copy button and the words 'Send this link yourself;
  // LeadRadar sends no message. It works once, for <INVITE_TTL_HOURS> hours.'"
  const linkInput = adminPage.getByLabel(`Invite link for ${inviteEmail}`);
  await expect(linkInput).toBeVisible();
  const link = await linkInput.inputValue();
  expect(link).toMatch(/^http:\/\/localhost:8080\/invite#.+/);
  await expect(
    adminPage.getByText(
      "Send this link yourself; LeadRadar sends no message. It works once, for 72 hours.",
    ),
  ).toBeVisible();
  await expect(adminPage.getByRole("button", { name: "Copy link" })).toBeVisible();
  await adminPage.getByRole("button", { name: "Done" }).click();

  const token = link.split("#", 2)[1];

  // FR-169/FR-170: the invite preview card names the inviter, role, invited email and age.
  const invitePage = await browser.newPage();
  await invitePage.goto(`/invite#${token}`);
  await expect(
    invitePage.locator('[aria-label="admin invited you to LeadRadar as Sales"]'),
  ).toBeAttached();
  await expect(invitePage.locator("figcaption", { hasText: inviteEmail })).toBeVisible();

  // FR-171: "the password hint states the minimum length the preview returns."
  const passwordHint = await invitePage
    .getByLabel("Password", { exact: false })
    .locator("xpath=following-sibling::*[1]")
    .textContent();
  const minLengthMatch = passwordHint?.match(/(\d+)/);
  expect(minLengthMatch, `expected a numeric minimum length in the password hint, got: ${passwordHint}`).toBeTruthy();
  const minLength = Number(minLengthMatch![1]);

  await invitePage.getByLabel("Display name", { exact: false }).fill("AC-78 E2E Invitee");
  await invitePage.getByLabel("Password", { exact: false }).fill("x".repeat(minLength));

  // FR-172: "A column beside the form rises one step for each character of the password up to a
  // line at the minimum length" - the accessible length readout reaches the minimum.
  await expect(invitePage.locator(".ai-col-count")).toHaveText(`${minLength}/${minLength}`);

  await invitePage.getByRole("button", { name: "Join LeadRadar" }).click();

  // "answers as API-01 would, sets the session cookie, creates an active Sales user" and opens
  // Prospects.
  await invitePage.waitForURL("**/prospects");

  const usersAfter = await browser.newPage();
  await signInViaUi(usersAfter, ADMIN_EMAIL, adminPassword());
  await usersAfter.waitForURL("**/prospects");
  await usersAfter.goto("/users");
  const row = usersAfter.locator("tbody tr", { hasText: inviteEmail });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Active")).toBeVisible();
  await expect(row.getByText("Sales")).toBeVisible();
});

test("AC-78 a used invite link no longer works", async ({ browser }) => {
  const adminPage = await browser.newPage();
  await signInViaUi(adminPage, ADMIN_EMAIL, adminPassword());
  await adminPage.waitForURL("**/prospects");
  await adminPage.goto("/users");
  await adminPage.getByRole("button", { name: "Invite user" }).click();
  const inviteEmail = `ac78-used-e2e-${Date.now()}@leadradar.local`;
  await adminPage.getByLabel("Email", { exact: false }).fill(inviteEmail);
  await adminPage.getByLabel("Role", { exact: false }).selectOption("SALES");
  await adminPage.getByRole("button", { name: "Create invite link" }).click();
  const link = await adminPage.getByLabel(`Invite link for ${inviteEmail}`).inputValue();
  const token = link.split("#", 2)[1];
  await adminPage.getByRole("button", { name: "Done" }).click();

  const firstUse = await browser.newPage();
  await firstUse.goto(`/invite#${token}`);
  await firstUse.getByLabel("Display name", { exact: false }).fill("AC-78 First Use");
  await firstUse.getByLabel("Password", { exact: false }).fill("x".repeat(12));
  await firstUse.getByRole("button", { name: "Join LeadRadar" }).click();
  await firstUse.waitForURL("**/prospects");

  // FR-169: "a 404 shows 'This invite link no longer works. Ask your Admin for a new one.' with
  // a link to Sign in and no form."
  const reused = await browser.newPage();
  await reused.goto(`/invite#${token}`);
  await expect(reused.getByText("This invite link no longer works.")).toBeVisible();
  await expect(reused.getByText("Ask your Admin for a new one.")).toBeVisible();
  await expect(reused.getByLabel("Display name", { exact: false })).toHaveCount(0);
  await expect(reused.getByRole("link", { name: "Sign in" })).toBeVisible();
});
