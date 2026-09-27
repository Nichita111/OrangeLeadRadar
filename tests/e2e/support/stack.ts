/**
 * Brings up the composed stack of docs/architecture/overview.md#runtime (docker compose up),
 * the same way tests/acceptance/conftest.py does for the pytest suite: FIXTURE_MODE=replay,
 * the clock injected through CLOCK_FILE, seeded through `make seed-demo`
 * (docs/architecture/overview.md#runtime). Nothing here is read from the implementation; the
 * routes and credentials come from docs/architecture/services/frontend.md#routes and
 * docs/architecture/overview.md#demo-dataset.
 *
 * Reuses tests/acceptance/docker/compose.override.yml, the same override the acceptance suite
 * uses, so both suites run the api and worker in the same configuration.
 */
import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

export const ROOT = path.resolve(__dirname, "..", "..", "..");
const BASE_COMPOSE = path.join(ROOT, "compose.yaml");
const OVERRIDE_COMPOSE = path.join(ROOT, "tests", "acceptance", "docker", "compose.override.yml");
export const WEB_PORT = 8080;
export const BASE_URL = `http://localhost:${WEB_PORT}`;
export const PROJECT = "lr-qa-e2e";
export const STATE_FILE = path.join(__dirname, "..", ".stack-env.json");

export interface StackEnv {
  [key: string]: string;
}

function randomToken(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function buildEnv(): StackEnv {
  const env: StackEnv = { ...(process.env as StackEnv) };
  env.POSTGRES_PASSWORD = env.POSTGRES_PASSWORD || "qa-" + randomToken();
  env.APP_DB_PASSWORD = env.APP_DB_PASSWORD || "qa-app-" + randomToken();
  // A key that is present but not a real secret: replay mode never calls out with it
  // (docs/architecture/interfaces.md#audit-and-health-shapes).
  env.OPENROUTER_API_KEY = env.OPENROUTER_API_KEY || "qa-fake-key-" + randomToken();
  env.LLM_CLASSIFIER_MODEL = env.LLM_CLASSIFIER_MODEL || "openai/gpt-4o-mini";
  env.LLM_EVIDENCE_MODEL = env.LLM_EVIDENCE_MODEL || "openai/gpt-4o-mini";
  env.LLM_OUTREACH_MODEL = env.LLM_OUTREACH_MODEL || "openai/gpt-4o-mini";
  // The demo users' passwords (docs/architecture/overview.md#demo-dataset), read by
  // `make seed-demo` (docs/architecture/services/api.md#runtime): at least
  // PASSWORD_MIN_LENGTH characters, never a real secret.
  env.SEED_ADMIN_PASSWORD = env.SEED_ADMIN_PASSWORD || "qa-admin-pw-" + randomToken();
  env.SEED_SALES_PASSWORD = env.SEED_SALES_PASSWORD || "qa-sales-pw-" + randomToken();
  // Sign-in shortcuts are not used here so this can stay off; declared so the frontend's
  // /config.json is deterministic across runs.
  env.DEMO_SIGN_IN = env.DEMO_SIGN_IN || "false";
  return env;
}

function compose(args: string[], env: StackEnv, timeoutMs = 3600_000): string {
  return execFileSync(
    "docker",
    ["compose", "-p", PROJECT, "-f", BASE_COMPOSE, "-f", OVERRIDE_COMPOSE, ...args],
    { cwd: ROOT, env: env as NodeJS.ProcessEnv, timeout: timeoutMs, encoding: "utf-8" },
  );
}

async function waitForHealth(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr: unknown;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${BASE_URL}/api/v1/health`);
      if (res.status === 200 || res.status === 503) return;
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error(`timed out waiting for the api to answer /health: ${String(lastErr)}`);
}

export async function startStack(): Promise<StackEnv> {
  const env = buildEnv();
  compose(["up", "-d", "--build", "db", "api", "worker", "web"], env);
  await waitForHealth(180_000);
  compose(["exec", "-T", "api", "leadradar-seed-demo"], env);
  fs.writeFileSync(STATE_FILE, JSON.stringify(env, null, 2));
  return env;
}

export function stopStack(): void {
  let env: StackEnv;
  try {
    env = JSON.parse(fs.readFileSync(STATE_FILE, "utf-8"));
  } catch {
    env = buildEnv();
  }
  try {
    compose(["down", "-v"], env);
  } finally {
    if (fs.existsSync(STATE_FILE)) fs.unlinkSync(STATE_FILE);
  }
}

export function loadEnv(): StackEnv {
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8"));
}
