import fs from "node:fs";
import { describe, expect, it } from "vitest";

const css = fs.readFileSync("src/styles/tokens.css", "utf8");
const blocks = css.split("@media (prefers-color-scheme: dark)");
const lightBlock = blocks[0] ?? "";
const darkBlock = blocks[1] ?? "";

function colors(block: string): Record<string, string> {
  return Object.fromEntries(
    [...block.matchAll(/--color-([\w-]+):\s*(#[0-9a-f]{6})/gi)].flatMap((match) =>
      match[1] !== undefined && match[2] !== undefined ? [[match[1], match[2]]] : [],
    ),
  );
}

function luminance(hex: string): number {
  const [red = 0, green = 0, blue = 0] = [1, 3, 5]
    .map((index) => Number.parseInt(hex.slice(index, index + 2), 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrast(first: string, second: string): number {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  const [lighter = 0, darker = 0] = values;
  return (lighter + 0.05) / (darker + 0.05);
}

function required(palette: Record<string, string>, key: string): string {
  const value = palette[key];
  if (value === undefined) throw new Error(`Missing token: ${key}`);
  return value;
}

describe("FR-108 token contrast", () => {
  it.each([
    ["light", colors(lightBlock)],
    ["dark", colors(darkBlock)],
  ] as const)("meets AA in %s", (_theme, palette) => {
    for (const background of [required(palette, "page"), required(palette, "surface")]) {
      for (const text of [
        required(palette, "text"),
        required(palette, "text-secondary"),
        required(palette, "text-tertiary"),
      ])
        expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(required(palette, "control-border"), background)).toBeGreaterThanOrEqual(3);
      expect(contrast(required(palette, "accent"), background)).toBeGreaterThanOrEqual(3);
    }
  });
});
