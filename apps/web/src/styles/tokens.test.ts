import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const srcRoot = resolve(process.cwd(), "src");
const tokensCss = readFileSync(join(srcRoot, "styles/tokens.css"), "utf8");

type Theme = Record<string, string>;

function declarations(block: string): Theme {
  const theme: Theme = {};
  for (const match of block.matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g)) {
    const [, name, value] = match;
    if (name !== undefined && value !== undefined) {
      theme[name] = value;
    }
  }
  return theme;
}

const mediaStart = tokensCss.indexOf("@media (prefers-color-scheme: dark)");
const light = declarations(tokensCss.slice(0, mediaStart));
const dark = { ...light, ...declarations(tokensCss.slice(mediaStart)) };

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  const [r = 0, g = 0, b = 0] = channels;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

// FR-108: text pairs 4.5:1, non-text pairs (control border, focus ring) 3:1.
const textPairs: [string, string][] = [
  ["text", "page"],
  ["text", "surface"],
  ["text-secondary", "page"],
  ["text-secondary", "surface"],
  ["text-tertiary", "page"],
  ["text-tertiary", "surface"],
  ["on-accent", "accent"],
  ["accent-ink", "accent-soft"],
  ["positive", "positive-soft"],
  ["negative", "negative-soft"],
  ["caution", "caution-soft"],
  ["cool", "cool-soft"],
  ["text", "highlight"],
  ["accent", "surface"],
  ["accent", "page"],
];
const nonTextPairs: [string, string][] = [
  ["control-border", "surface"],
  ["control-border", "page"],
  ["accent", "surface"],
  ["accent", "page"],
];

describe("tokens.css contrast (FR-108, FR-016)", () => {
  for (const [themeName, theme] of [
    ["light", light],
    ["dark", dark],
  ] as const) {
    it.each(textPairs)(`${themeName}: %s on %s meets 4.5:1`, (fg, bg) => {
      const fgValue = theme[fg];
      const bgValue = theme[bg];
      expect(fgValue, `token ${fg}`).toBeDefined();
      expect(bgValue, `token ${bg}`).toBeDefined();
      expect(contrast(fgValue ?? "", bgValue ?? "")).toBeGreaterThanOrEqual(4.5);
    });

    it.each(nonTextPairs)(`${themeName}: %s on %s meets 3:1`, (fg, bg) => {
      expect(contrast(theme[fg] ?? "", theme[bg] ?? "")).toBeGreaterThanOrEqual(3);
    });
  }
});

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? sourceFiles(path) : [path];
  });
}

describe("colour literals (FR-106)", () => {
  it("no source file other than tokens.css contains a hex, rgb( or hsl( colour", () => {
    const offenders = sourceFiles(srcRoot).filter((path) => {
      if (path.endsWith("tokens.css") || path.endsWith(".gen.ts") || path.endsWith(".json")) {
        return false;
      }
      if (/\.test\.tsx?$/.test(path)) {
        return false;
      }
      return /#[0-9A-Fa-f]{3,8}\b|\brgba?\(|\bhsla?\(/.test(readFileSync(path, "utf8"));
    });
    expect(offenders).toEqual([]);
  });
});
