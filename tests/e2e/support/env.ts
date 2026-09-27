import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// The demo users' passwords (docs/architecture/overview.md#demo-dataset: "passwords from
// SEED_ADMIN_PASSWORD and SEED_SALES_PASSWORD"), read from the repo root .env the already-running
// composed stack was started with (docs/architecture/services/api.md#runtime); never printed,
// logged or written anywhere else.
const ROOT = path.resolve(fileURLToPath(new URL("../../../", import.meta.url)));

function dotenvValue(name: string): string {
  const text = readFileSync(path.join(ROOT, ".env"), "utf-8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return trimmed.slice(name.length + 1);
    }
  }
  throw new Error(`${name} not found in the repo root .env`);
}

export const ADMIN_EMAIL = "admin@leadradar.local";
export const SALES_EMAIL = "sales@leadradar.local";

export function adminPassword(): string {
  return dotenvValue("SEED_ADMIN_PASSWORD");
}

export function salesPassword(): string {
  return dotenvValue("SEED_SALES_PASSWORD");
}
