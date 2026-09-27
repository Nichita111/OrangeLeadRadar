import * as THREE from "three";

import { ACCOUNTS, DHL } from "./sceneData";

/**
 * The radar both WebGL scenes stand on — the Landing scene (FR-164) and Accept invite (FR-172):
 * the colour tokens, the accounts laid out on a disc of six sectors, the floor grid, the disc and
 * the sprite textures. Only the scene modules import it (FR-166).
 */

export const TAU = Math.PI * 2;
/** The radius of the disc's outer ring. */
export const R = 5.6;
/** One of the disc's six sectors. */
export const SEC = TAU / 6;

export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const ease = (t: number) => t * t * (3 - 2 * t);

export function need<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined) {
    throw new Error(`Radar scene: ${what} is missing.`);
  }
  return value;
}

/** The colour tokens of Visual language, read from the page; both scenes force the dark ones. */
export function readTones() {
  const style = getComputedStyle(document.documentElement);
  const tone = (name: string) => new THREE.Color(style.getPropertyValue(`--${name}`).trim());
  return {
    page: tone("page"),
    line: tone("border"),
    line2: tone("border").lerp(tone("control-border"), 0.35),
    grey: tone("text-tertiary"),
    text2: tone("text-secondary"),
    text: tone("text"),
    accent: tone("accent"),
    ink: tone("accent-ink"),
    fill: tone("surface"),
    fill2: tone("border"),
    accentSoft: tone("accent-soft"),
    cool: tone("cool"),
    coolSoft: tone("cool-soft"),
  };
}
export type Tones = ReturnType<typeof readTones>;

export const hex = (color: THREE.Color) => `#${color.getHexString()}`;

/** A repeatable random sequence, so the scene looks the same on every visit. */
export function seededRandom(seed: number): () => number {
  let state = seed;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}

/** Lines write no depth: a line faded to nothing would still cut a hole through what is drawn after it. */
export const lineMat = (color: THREE.Color, opacity = 1) =>
  new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false });

/** The demo accounts at their places on the disc. */
export function layoutAccounts(rnd: () => number) {
  const accounts = ACCOUNTS.map(([n, s, prio, band, docs, rel], i) => ({
    n,
    s,
    prio,
    band,
    docs,
    rel,
    i,
    ang: 0,
    r: 0,
    x: 0,
    z: 0,
  }));
  for (let s = 0; s < 6; s++) {
    const members = accounts.filter((a) => a.s === s);
    members.forEach((a, j) => {
      a.ang = s * SEC + ((j + 0.5) / members.length) * SEC * 0.8 + SEC * 0.1;
      const r = 2.1 + rnd() * 3.0;
      a.r = a.i === DHL ? 2.6 : r;
      a.x = Math.cos(a.ang) * a.r;
      a.z = Math.sin(a.ang) * a.r;
    });
  }
  return accounts;
}

/** The floor: a grid under the disc, fading into the Page toward its edges. */
export function buildFloor(C: Tones) {
  const FLOOR = 14;
  const CELL = 0.7;
  const positions: number[] = [];
  const colours: number[] = [];
  const toneAt = (x: number, z: number) =>
    C.line.clone().lerp(C.page, clamp((Math.hypot(x, z) - 4) / (FLOOR - 4)));
  for (let v = -FLOOR; v <= FLOOR + 1e-6; v += CELL) {
    for (let u = -FLOOR; u < FLOOR - 1e-6; u += CELL) {
      for (const [x1, z1, x2, z2] of [
        [u, v, u + CELL, v],
        [v, u, v, u + CELL],
      ] as const) {
        positions.push(x1, -0.02, z1, x2, -0.02, z2);
        const a = toneAt(x1, z1);
        const b = toneAt(x2, z2);
        colours.push(a.r, a.g, a.b, b.r, b.g, b.b);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colours, 3));
  const material = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 1,
    depthWrite: false,
  });
  return { floor: new THREE.LineSegments(geometry, material), floorMat: material };
}

/** The disc: range rings and a sector tick at each boundary, with each line's own opacity. */
export function buildDisc(C: Tones) {
  const disc = new THREE.Group();
  [1.4, 2.8, 4.2, R].forEach((r, i) => {
    const pts: THREE.Vector3[] = [];
    for (let k = 0; k <= 160; k++) {
      const a = (k / 160) * TAU;
      pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r));
    }
    disc.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        lineMat(i === 3 ? C.line2 : C.line),
      ),
    );
  });
  for (let s = 0; s < 6; s++) {
    const a = s * SEC;
    disc.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(Math.cos(a) * 1.4, 0, Math.sin(a) * 1.4),
          new THREE.Vector3(Math.cos(a) * R, 0, Math.sin(a) * R),
        ]),
        lineMat(C.line),
      ),
    );
  }
  const discMats: [THREE.Material, number][] = [];
  disc.traverse((o) => {
    if (o instanceof THREE.Line) {
      const m = o.material as THREE.Material;
      discMats.push([m, m.opacity]);
    }
  });
  return { disc, discMats };
}

/** The round dot and the soft glow the points are drawn with, as masks their material tints. */
export function spriteTextures(C: Tones) {
  const mask = (alpha: number) =>
    `${hex(C.text)}${Math.round(alpha * 255)
      .toString(16)
      .padStart(2, "0")}`;
  const sprite = (paint: (g: CanvasRenderingContext2D) => void) => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    paint(need(c.getContext("2d"), "2D canvas"));
    return new THREE.CanvasTexture(c);
  };
  const dotTex = sprite((g) => {
    g.beginPath();
    g.arc(32, 32, 28, 0, TAU);
    g.fillStyle = mask(1);
    g.fill();
  });
  const glowTex = sprite((g) => {
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, mask(1));
    gr.addColorStop(0.18, mask(0.55));
    gr.addColorStop(0.5, mask(0.12));
    gr.addColorStop(1, mask(0));
    g.fillStyle = gr;
    g.fillRect(0, 0, 64, 64);
  });
  return { dotTex, glowTex };
}

/** A points cloud drawn with the round dot, coloured per point. */
export function dotPoints(positions: Float32Array, colours: Float32Array, dotTex: THREE.Texture) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  return new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      size: 0.19,
      map: dotTex,
      vertexColors: true,
      transparent: true,
      alphaTest: 0.4,
      depthWrite: false,
    }),
  );
}

/** Frees every geometry, material and texture of a scene, and the renderer. */
export function disposeScene(scene: THREE.Scene, renderer: THREE.WebGLRenderer) {
  scene.traverse((o) => {
    if (o instanceof THREE.Mesh || o instanceof THREE.Line || o instanceof THREE.Points) {
      (o.geometry as THREE.BufferGeometry).dispose();
      const m = o.material as THREE.Material & { map?: THREE.Texture | null };
      m.map?.dispose();
      m.dispose();
    }
  });
  renderer.dispose();
}
