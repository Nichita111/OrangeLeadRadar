import { Page, expect } from "@playwright/test";
import { loadEnv } from "./stack";

/** Demo dataset users (docs/architecture/overview.md#demo-dataset). */
export const DEMO_USERS = {
  ADMIN: { email: "admin@leadradar.local", passwordKey: "SEED_ADMIN_PASSWORD" as const },
  SALES: { email: "sales@leadradar.local", passwordKey: "SEED_SALES_PASSWORD" as const },
};

export type Role = keyof typeof DEMO_USERS;

/**
 * Signs in through Sign in (`/login`, docs/features/identity-and-access.md#sign-in) with the
 * demo dataset credentials, following FL-19 step 2. Leaves the browser on the return page
 * (`/prospects` by default, FR-093).
 */
export async function signIn(page: Page, role: Role): Promise<void> {
  const env = loadEnv();
  const user = DEMO_USERS[role];
  const password = env[user.passwordKey];
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/prospects/, { timeout: 15_000 });
}
