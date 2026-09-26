import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = process.cwd();
const interfacesPath = resolve(webRoot, "../../docs/architecture/interfaces.md");

interface OpenApiDocument {
  paths: Record<string, Record<string, unknown>>;
  components: { schemas: Record<string, unknown> };
}

function readJson(path: string): OpenApiDocument {
  return JSON.parse(readFileSync(path, "utf8")) as OpenApiDocument;
}

function freshGeneration(input: string): string {
  const out = join(mkdtempSync(join(tmpdir(), "leadradar-gen-")), "schema.gen.ts");
  execFileSync("npx", ["openapi-typescript", input, "-o", out], { cwd: webRoot, stdio: "pipe" });
  return readFileSync(out, "utf8");
}

/** The `API-nn` rows of interfaces.md as `method /api/v1<path>`. */
function contractRows(ids: string[]): string[] {
  const rows: string[] = [];
  for (const line of readFileSync(interfacesPath, "utf8").split("\n")) {
    const match = /^\| `(API-\d+)` \| (\w+) \| `([^`]+)` \|/.exec(line);
    const id = match?.[1];
    if (id !== undefined && ids.includes(id)) {
      rows.push(`${(match?.[2] ?? "").toLowerCase()} /api/v1${match?.[3] ?? ""}`);
    }
  }
  return rows.sort();
}

/** The `details.` names of the Envelope table of interfaces.md. */
function envelopeDetailNames(): string[] {
  const names = new Set<string>();
  const text = readFileSync(interfacesPath, "utf8");
  const start = text.indexOf("**Envelope.**");
  const end = text.indexOf("Degraded behaviour is an explicit error", start);
  for (const match of text.slice(start, end).matchAll(/`details\.(\w+)(?:\[\])?`/g)) {
    const name = match[1];
    if (name !== undefined) {
      names.add(name);
    }
  }
  return [...names].sort();
}

/** The `details.dependency` column of the Dependencies table of interfaces.md. */
function documentedDependencies(): string[] {
  const values: string[] = [];
  for (const line of readFileSync(interfacesPath, "utf8").split("\n")) {
    const match = /^\| `UPSTREAM_UNAVAILABLE` \| `(\w+)` \|/.exec(line);
    if (match?.[1] !== undefined) {
      values.push(match[1]);
    }
  }
  return values;
}

describe("contract files", () => {
  it("the committed schema.gen.ts equals a fresh generation from apps/api/openapi.json", () => {
    expect(readFileSync(resolve(webRoot, "src/api/schema.gen.ts"), "utf8")).toBe(
      freshGeneration("../api/openapi.json"),
    );
  });

  it("G13: the committed pending/schema.gen.ts equals a fresh generation from the fragment", () => {
    expect(readFileSync(resolve(webRoot, "src/api/pending/schema.gen.ts"), "utf8")).toBe(
      freshGeneration("src/api/pending/openapi.json"),
    );
  });

  it("G13, R3: the fragment's operations are exactly API-39, API-40 and API-42 to API-45 of interfaces.md", () => {
    const fragment = readJson(resolve(webRoot, "src/api/pending/openapi.json"));
    const operations = Object.entries(fragment.paths).flatMap(([path, item]) =>
      Object.keys(item).map((method) => `${method} ${path}`),
    );
    expect(operations.sort()).toEqual(
      contractRows(["API-39", "API-40", "API-42", "API-43", "API-44", "API-45"]),
    );
  });

  it("G14: the fragment's details is closed and names exactly the details of the Envelope table", () => {
    const fragment = readJson(resolve(webRoot, "src/api/pending/openapi.json"));
    const envelope = fragment.components.schemas["ErrorEnvelope"] as {
      properties: { error: { properties: { details: Record<string, unknown> } } };
    };
    const details = envelope.properties.error.properties.details as {
      additionalProperties: boolean;
      properties: Record<string, unknown>;
    };
    expect(details.additionalProperties).toBe(false);
    expect(Object.keys(details.properties).sort()).toEqual(envelopeDetailNames());
  });

  it("R-6, G14: the fragment's details.dependency enum is the Dependencies table of interfaces.md", () => {
    const fragment = readJson(resolve(webRoot, "src/api/pending/openapi.json"));
    const envelope = fragment.components.schemas["ErrorEnvelope"] as {
      properties: {
        error: { properties: { details: { properties: { dependency: { enum: string[] } } } } };
      };
    };
    const dependency = envelope.properties.error.properties.details.properties.dependency;
    expect(documentedDependencies()).not.toEqual([]);
    expect(dependency.enum).toEqual(documentedDependencies());
  });

  it("tripwire: apps/api/openapi.json declares no path of the fragment", () => {
    const fragment = readJson(resolve(webRoot, "src/api/pending/openapi.json"));
    const snapshot = readJson(resolve(webRoot, "../api/openapi.json"));
    const declared = Object.keys(fragment.paths).filter((path) => path in snapshot.paths);
    expect(declared, "delete src/api/pending/ as the design's removal steps say").toEqual([]);
  });
});
