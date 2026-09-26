import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = process.cwd();
const srcRoot = resolve(webRoot, "src");
const frontendPath = resolve(webRoot, "../../docs/architecture/services/frontend.md");

function filesUnder(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? filesUnder(path) : [path];
  });
}

/** Source files a rule applies to: no tests and no generated code. */
function shippedSources(extension: RegExp): string[] {
  return filesUnder(srcRoot).filter(
    (path) => extension.test(path) && !/\.test\.tsx?$/.test(path) && !path.endsWith(".gen.ts"),
  );
}

function inMotion(path: string): boolean {
  return relative(srcRoot, path).startsWith(`components${sep}motion${sep}`);
}

function contains(path: string, pattern: RegExp): boolean {
  return pattern.test(readFileSync(path, "utf8"));
}

// The token table of frontend Visual language: the row label and the token names its cells give.
const TOKEN_NAMES: Record<string, string[]> = {
  Page: ["page"],
  Surface: ["surface"],
  Border: ["border"],
  "Control border": ["control-border"],
  Text: ["text"],
  "Text secondary": ["text-secondary"],
  "Text tertiary": ["text-tertiary"],
  Accent: ["accent"],
  "On accent": ["on-accent"],
  "Accent soft, ink": ["accent-soft", "accent-ink"],
  "Positive, soft": ["positive", "positive-soft"],
  "Negative, soft": ["negative", "negative-soft"],
  "Caution, soft": ["caution", "caution-soft"],
  "Cool, soft": ["cool", "cool-soft"],
  Highlight: ["highlight"],
};

type Theme = Record<string, string>;

function hexDeclarations(block: string): Theme {
  const theme: Theme = {};
  for (const match of block.matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g)) {
    if (match[1] !== undefined && match[2] !== undefined) {
      theme[match[1]] = match[2].toUpperCase();
    }
  }
  return theme;
}

function hexValues(cell: string): string[] {
  return [...cell.matchAll(/`(#[0-9A-Fa-f]{6})`/g)].map((match) => (match[1] ?? "").toUpperCase());
}

function documentedTokens(): { light: Theme; dark: Theme } {
  const light: Theme = {};
  const dark: Theme = {};
  for (const line of readFileSync(frontendPath, "utf8").split("\n")) {
    const cells = line.split("|").map((cell) => cell.trim());
    const names = TOKEN_NAMES[cells[1] ?? ""];
    if (names === undefined || cells.length < 6) {
      continue;
    }
    const lightValues = hexValues(cells[2] ?? "");
    const darkValues = hexValues(cells[3] ?? "");
    names.forEach((name, index) => {
      light[name] = lightValues[index] ?? "";
      dark[name] = darkValues[index] ?? "";
    });
  }
  return { light, dark };
}

describe("one accent token (FR-107)", () => {
  it("the hex-valued custom properties of tokens.css are the token table of frontend Visual language, in both themes", () => {
    const css = readFileSync(join(srcRoot, "styles/tokens.css"), "utf8");
    const mediaStart = css.indexOf("@media (prefers-color-scheme: dark)");
    const documented = documentedTokens();
    expect(Object.keys(documented.light)).toHaveLength(Object.values(TOKEN_NAMES).flat().length);
    expect(hexDeclarations(css.slice(0, mediaStart))).toEqual(documented.light);
    expect(hexDeclarations(css.slice(mediaStart))).toEqual(documented.dark);
  });

  it("the table has one accent: Accent, On accent, and Accent soft with its ink", () => {
    const accents = Object.keys(documentedTokens().light).filter((name) => name.includes("accent"));
    expect(accents.sort()).toEqual(["accent", "accent-ink", "accent-soft", "on-accent"]);
  });
});

describe("no external font or icon (FR-109)", () => {
  it("index.html and every stylesheet hold no http(s) URL", () => {
    const files = [join(webRoot, "index.html"), ...shippedSources(/\.css$/)];
    expect(files.filter((path) => contains(path, /https?:\/\//))).toEqual([]);
  });

  it("no source file imports a font or an icon from a URL", () => {
    const offenders = shippedSources(/\.(ts|tsx|css)$/).filter((path) =>
      contains(path, /(?:from|import)\s*\(?\s*["'](?:https?:)?\/\//),
    );
    expect(offenders).toEqual([]);
  });
});

describe("Motion patterns only (FR-124, FR-126)", () => {
  it("FR-124: motion and ogl are imported only under components/motion", () => {
    const offenders = shippedSources(/\.tsx?$/).filter(
      (path) => !inMotion(path) && contains(path, /from\s+["'](?:motion(?:\/[\w-]+)?|ogl)["']/),
    );
    expect(offenders).toEqual([]);
  });

  it("FR-124: no transition, animate- class or keyframes outside components/motion", () => {
    const offenders = shippedSources(/\.(tsx?|css)$/).filter(
      (path) =>
        !inMotion(path) && contains(path, /\btransition\b|\btransition-|animate-|@keyframes/),
    );
    expect(offenders).toEqual([]);
  });

  it("FR-126: nothing loops except the Motion Aurora frame loop", () => {
    const offenders = shippedSources(/\.(tsx?|css)$/).filter((path) =>
      contains(path, /repeat:\s*Infinity|\binfinite\b|animate-(?:spin|pulse|ping|bounce)/),
    );
    expect(offenders).toEqual([]);
  });
});

describe("shader colours (FR-106)", () => {
  it("no GLSL mix( names a vec3 of numeric literals only", () => {
    const offenders = shippedSources(/\.tsx?$/).filter((path) =>
      contains(path, /mix\(\s*vec3\(\s*[\d.]+\s*(?:,\s*[\d.]+\s*){0,2}\)/),
    );
    expect(offenders).toEqual([]);
  });
});
