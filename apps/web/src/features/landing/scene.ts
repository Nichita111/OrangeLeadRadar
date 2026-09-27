import anime from "animejs";
import * as THREE from "three";

import {
  ACCOUNTS,
  DHL,
  DHL_SCORES,
  FLOWS,
  LUFTHANSA,
  QUOTE,
  QUOTE_SOURCE,
  RULES,
  SOURCES,
  TRANSLATION,
  type SceneBand,
} from "./sceneData";

/**
 * The Landing scene (WF-27, FR-161, FR-164, FR-165): one three.js scene over the pinned stage and one
 * Anime.js timeline that scroll scrubs, step k centred at 1000 k. It draws into `canvas` and places
 * its labels, quote card and Prospects list in `overlay`. Only this module imports three.js and
 * Anime.js (FR-166).
 */
export interface SceneTargets {
  scroll: HTMLElement;
  stage: HTMLElement;
  canvas: HTMLCanvasElement;
  overlay: HTMLElement;
  steps: number;
  reduced: boolean;
}

const TAU = Math.PI * 2;
const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => t * t * (3 - 2 * t);

function need<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined) {
    throw new Error(`Landing scene: ${what} is missing.`);
  }
  return value;
}

// Phosphor icons (FR-111): flame fill, sun, snowflake.
const ICON: Record<SceneBand, string> = {
  hot: '<svg viewBox="0 0 256 256" fill="currentColor" aria-hidden="true"><path d="M173.79,51.48a221.25,221.25,0,0,0-41.67-34.34,8,8,0,0,0-8.24,0A221.25,221.25,0,0,0,82.21,51.48C54.59,80.48,40,112.47,40,144a88,88,0,0,0,176,0C216,112.47,201.410,80.48,173.790,51.48ZM96,184c0-27.67,22.53-47.28,32-54.3,9.48,7,32,26.63,32,54.3a32,32,0,0,1-64,0Z"/></svg>',
  warm: '<svg viewBox="0 0 256 256" fill="currentColor" aria-hidden="true"><path d="M120,40V16a8,8,0,0,1,16,0V40a8,8,0,0,1-16,0Zm72,88a64,64,0,1,1-64-64A64.07,64.07,0,0,1,192,128Zm-16,0a48,48,0,1,0-48,48A48.050,48.050,0,0,0,176,128ZM58.340,69.660A8,8,0,0,0,69.660,58.340l-16-16A8,8,0,0,0,42.340,53.660Zm0,116.680-16,16a8,8,0,0,0,11.320,11.320l16-16a8,8,0,0,0-11.320-11.320ZM192,72a8,8,0,0,0,5.660-2.340l16-16a8,8,0,0,0-11.320-11.320l-16,16A8,8,0,0,0,192,72Zm5.660,114.340a8,8,0,0,0-11.320,11.320l16,16a8,8,0,0,0,11.320-11.320ZM48,128a8,8,0,0,0-8-8H16a8,8,0,0,0,0,16H40A8,8,0,0,0,48,128Zm80,80a8,8,0,0,0-8,8v24a8,8,0,0,0,16,0V216A8,8,0,0,0,128,208Zm112-88H216a8,8,0,0,0,0,16h24a8,8,0,0,0,0-16Z"/></svg>',
  cold: '<svg viewBox="0 0 256 256" fill="currentColor" aria-hidden="true"><path d="M223.77,150.09a8,8,0,0,1-5.86,9.68l-24.64,6,6.46,24.11a8,8,0,0,1-5.66,9.8A8.25,8.25,0,0,1,192,200a8,8,0,0,1-7.72-5.93l-7.72-28.8L136,141.86v46.83l21.66,21.65a8,8,0,0,1-11.32,11.32L128,203.31l-18.34,18.35a8,8,0,0,1-11.32-11.32L120,188.69V141.86L79.45,165.27l-7.72,28.8A8,8,0,0,1,64,200a8.25,8.25,0,0,1-2.08-.27,8,8,0,0,1-5.66-9.8l6.46-24.11-24.64-6a8,8,0,0,1,3.82-15.54l29.45,7.23L112,128,71.36,104.54l-29.45,7.23A7.85,7.85,0,0,1,40,112a8,8,0,0,1-1.91-15.77l24.64-6L56.27,66.07a8,8,0,0,1,15.46-4.14l7.72,28.8L120,114.14V67.31L98.34,45.66a8,8,0,0,1,11.32-11.32L128,52.69l18.34-18.35a8,8,0,0,1,11.32,11.32L136,67.31v46.83l40.55-23.41,7.72-28.8a8,8,0,0,1,15.46,4.14l-6.46,24.11,24.64,6A8,8,0,0,1,216,112a7.85,7.85,0,0,1-1.91-.23l-29.45-7.23L144,128l40.64,23.46,29.45-7.23A8,8,0,0,1,223.77,150.09Z"/></svg>',
};
const BAND_LABEL: Record<SceneBand, string> = { hot: "Hot", warm: "Warm", cold: "Cold" };
const chip = (band: SceneBand) =>
  `<span class="lr-chip lr-${band}">${ICON[band]}${BAND_LABEL[band]}</span>`;
const bar = (width: number, right = false) =>
  `<div class="lr-bar" style="width:${String(width)}px${right ? ";margin-left:auto" : ""}"></div>`;

const OVERLAY = `
  <div data-part="names"></div>
  <div data-part="ports"></div>
  <div data-part="rules"></div>
  <div class="lr-cnt" data-part="cnt-fit"><strong data-part="n-fit">0</strong><span>Fit</span></div>
  <div class="lr-cnt" data-part="cnt-int"><strong data-part="n-int">0</strong><span>Intent</span></div>
  <div class="lr-prio" data-part="prio">${chip("hot")}<strong data-part="n-prio">0</strong><span>Priority</span></div>
  <div class="lr-card" data-part="card">
    <p class="lr-q">${QUOTE}</p>
    <p class="lr-t"><b>EN</b><span data-part="trans"></span></p>
    <div class="lr-src" data-part="src">${QUOTE_SOURCE}</div>
  </div>
  <div class="lr-list" data-part="list">
    <div class="lr-list-head">
      <h3>Prospects <span>for Intelligent Automation</span></h3>
      <div class="lr-seg"><span class="lr-on">All 6</span><span>Hot 1</span><span>Warm 2</span><span>Cold 3</span></div>
    </div>
    <table>
      <thead><tr><th>#</th><th>Account</th><th>Band</th><th class="lr-n">Priority</th><th class="lr-n">Fit</th><th class="lr-n">Intent</th><th>Top signals</th></tr></thead>
      <tbody>
        <tr>
          <td class="lr-rank">1</td>
          <td class="lr-an"><b data-part="row-0">DHL Group</b><span>Germany, Logistics</span></td>
          <td>${chip("hot")}</td>
          <td class="lr-n lr-big">78</td><td class="lr-n">88</td><td class="lr-n">72</td>
          <td><div class="lr-sig"><span>AI projects, Strong <i>3 wk</i></span><span>Cost programme, Clear <i>2 mo</i></span></div></td>
        </tr>
        <tr>
          <td class="lr-rank">2</td>
          <td class="lr-an"><b data-part="row-1">Lufthansa Group</b><span>Germany, Aviation</span></td>
          <td>${chip("warm")}</td>
          <td class="lr-n lr-big">58</td><td class="lr-n">88</td><td class="lr-n">38</td>
          <td><div class="lr-sig"><span>Cost programme, Strong <i>6 wk</i></span></div></td>
        </tr>
        <tr class="lr-more"><td class="lr-rank">3</td><td>${bar(110)}</td><td>${chip("warm")}</td><td>${bar(22, true)}</td><td>${bar(22, true)}</td><td>${bar(22, true)}</td><td>${bar(150)}</td></tr>
        <tr class="lr-more"><td class="lr-rank">4</td><td>${bar(84)}</td><td>${chip("cold")}</td><td>${bar(22, true)}</td><td>${bar(22, true)}</td><td>${bar(22, true)}</td><td>${bar(120)}</td></tr>
      </tbody>
    </table>
  </div>
  <div class="lr-flyer" data-part="fly-0">DHL Group</div>
  <div class="lr-flyer" data-part="fly-1">Lufthansa Group</div>`;

const KEYS = [
  "src",
  "tilt",
  "read",
  "sift",
  "lift",
  "card",
  "typeT",
  "focus",
  "quoteOut",
  "docsOut",
  "g0",
  "g1",
  "g2",
  "g3",
  "g4",
  "g5",
  "fitN",
  "intN",
  "prioLine",
  "unfocus",
  "collapse",
  "rise",
  "sort",
  "flat",
  "list",
  "fly",
] as const;
type Key = (typeof KEYS)[number];

/** Mounts the scene; answers null when the browser has no WebGL (FR-165). */
export function mountScene(targets: SceneTargets): (() => void) | null {
  const { scroll, stage, canvas, overlay, steps, reduced } = targets;
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch {
    return null;
  }

  // Colours are the tokens of Visual language; Landing forces the dark ones (FR-106, FR-164).
  const style = getComputedStyle(document.documentElement);
  const css = (name: string) => style.getPropertyValue(`--${name}`).trim();
  const tone = (name: string) => new THREE.Color(css(name));
  const mixed = (a: string, b: string, t: number) => tone(a).lerp(tone(b), t);
  const C = {
    page: tone("page"),
    line: tone("border"),
    line2: mixed("border", "control-border", 0.35),
    grey: tone("text-tertiary"),
    text2: tone("text-secondary"),
    text: tone("text"),
    accent: tone("accent"),
    ink: tone("accent-ink"),
    fill: tone("surface"),
    fill2: tone("border"),
  };
  const hex = (color: THREE.Color) => `#${color.getHexString()}`;
  // Sprite masks are drawn in Text and tinted by their material.
  const mask = (alpha: number) =>
    `${hex(C.text)}${Math.round(alpha * 255)
      .toString(16)
      .padStart(2, "0")}`;

  overlay.innerHTML = OVERLAY;
  const part = (name: string) =>
    need(overlay.querySelector<HTMLElement>(`[data-part="${name}"]`), name);

  const DPR = Math.min(devicePixelRatio, navigator.hardwareConcurrency <= 4 ? 1.25 : 2);
  renderer.setPixelRatio(DPR);
  renderer.setClearColor(C.page, 1);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
  // Lines write no depth: a line faded to nothing would still cut a hole through what is drawn after it.
  const lineMat = (color: THREE.Color, opacity = 1) =>
    new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
  const basic = (color: THREE.Color, opacity = 1) =>
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity });

  let seed = 5;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

  // The accounts on a disc of six sectors
  const R = 5.6;
  const SEC = TAU / 6;
  const A = ACCOUNTS.map(([n, s, prio, band, docs, rel], i) => ({
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
    rankIdx: 0,
    skyX: 0,
    sx: 0,
    sy: 0,
  }));
  for (let s = 0; s < 6; s++) {
    const members = A.filter((a) => a.s === s);
    members.forEach((a, j) => {
      a.ang = s * SEC + ((j + 0.5) / members.length) * SEC * 0.8 + SEC * 0.1;
      const r = 2.1 + rnd() * 3.0;
      a.r = a.i === DHL ? 2.6 : r;
      a.x = Math.cos(a.ang) * a.r;
      a.z = Math.sin(a.ang) * a.r;
    });
  }
  [...A].sort((a, b) => b.prio - a.prio).forEach((a, k) => (a.rankIdx = k));
  const dA = need(A[DHL], "DHL Group");
  const PORTS = SOURCES.map((p) => ({
    ...p,
    x: Math.cos(p.angle) * 6.7,
    z: Math.sin(p.angle) * 6.7,
  }));

  // One timeline; step k is centred at t = 1000 k
  const S = Object.fromEntries(KEYS.map((k) => [k, 0])) as Record<Key, number>;
  const tl = anime.timeline({ autoplay: false, easing: "easeInOutSine" });
  const at = (k: Key, t: number, d: number, e?: string) =>
    tl.add({ targets: S, [k]: [0, 1], duration: d, ...(e === undefined ? {} : { easing: e }) }, t);
  at("src", 250, 700);
  at("tilt", 1200, 450);
  at("read", 1250, 700, "linear");
  at("sift", 2250, 700, "linear");
  at("focus", 3200, 400);
  at("lift", 3250, 280);
  at("card", 3450, 220, "easeOutCubic");
  at("typeT", 3680, 280, "linear");
  at("quoteOut", 4120, 160);
  at("docsOut", 4180, 220);
  for (let k = 0; k < 6; k++) {
    at(`g${String(k)}` as Key, 4330 + k * 95 + (k > 3 ? 60 : 0), 170, "easeOutCubic");
  }
  at("fitN", 4330, 420, "easeOutQuad");
  at("intN", 4710, 220, "easeOutQuad");
  at("prioLine", 4820, 150);
  at("unfocus", 5200, 420);
  at("collapse", 5200, 170);
  at("rise", 5300, 350, "easeOutCubic");
  at("sort", 5620, 330);
  at("flat", 6250, 300);
  at("list", 6400, 250);
  at("fly", 6500, 450);
  const TOTAL = (steps - 1) * 1000;

  // The floor: a grid under the disc, fading into the Page toward its edges
  const FLOOR = 14;
  const CELL = 0.7;
  const floorPos: number[] = [];
  const floorCol: number[] = [];
  const floorTone = (x: number, z: number) =>
    C.line.clone().lerp(C.page, clamp((Math.hypot(x, z) - 4) / (FLOOR - 4)));
  for (let v = -FLOOR; v <= FLOOR + 1e-6; v += CELL) {
    for (let u = -FLOOR; u < FLOOR - 1e-6; u += CELL) {
      for (const [x1, z1, x2, z2] of [
        [u, v, u + CELL, v],
        [v, u, v, u + CELL],
      ] as const) {
        floorPos.push(x1, -0.02, z1, x2, -0.02, z2);
        const a = floorTone(x1, z1);
        const b = floorTone(x2, z2);
        floorCol.push(a.r, a.g, a.b, b.r, b.g, b.b);
      }
    }
  }
  const floorGeo = new THREE.BufferGeometry();
  floorGeo.setAttribute("position", new THREE.Float32BufferAttribute(floorPos, 3));
  floorGeo.setAttribute("color", new THREE.Float32BufferAttribute(floorCol, 3));
  const floorMat = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 1,
    depthWrite: false,
  });
  const floor = new THREE.LineSegments(floorGeo, floorMat);
  scene.add(floor);

  // The disc: range rings and a sector tick at each boundary
  const disc = new THREE.Group();
  scene.add(disc);
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

  // Account points
  const spriteTexture = (paint: (g: CanvasRenderingContext2D) => void) => {
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    paint(need(c.getContext("2d"), "2D canvas"));
    return new THREE.CanvasTexture(c);
  };
  const dotTex = spriteTexture((g) => {
    g.beginPath();
    g.arc(32, 32, 28, 0, TAU);
    g.fillStyle = mask(1);
    g.fill();
  });
  const glowTex = spriteTexture((g) => {
    const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, mask(1));
    gr.addColorStop(0.18, mask(0.55));
    gr.addColorStop(0.5, mask(0.12));
    gr.addColorStop(1, mask(0));
    g.fillStyle = gr;
    g.fillRect(0, 0, 64, 64);
  });
  const glowMat = (color: THREE.Color, size: number) =>
    new THREE.PointsMaterial({
      size,
      map: glowTex,
      color,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      opacity: 0,
    });
  const ptGeo = new THREE.BufferGeometry();
  const ptPos = new Float32Array(A.length * 3);
  const ptCol = new Float32Array(A.length * 3);
  A.forEach((a, i) => {
    ptPos.set([a.x, 0.01, a.z], i * 3);
  });
  ptGeo.setAttribute("position", new THREE.BufferAttribute(ptPos, 3));
  ptGeo.setAttribute("color", new THREE.BufferAttribute(ptCol, 3));
  const points = new THREE.Points(
    ptGeo,
    new THREE.PointsMaterial({
      size: 0.19,
      map: dotTex,
      vertexColors: true,
      transparent: true,
      alphaTest: 0.4,
      depthWrite: false,
    }),
  );
  scene.add(points);

  // Sources: a curve from each source to each account it serves, and a packet travelling along it
  const curves: {
    curve: THREE.QuadraticBezierCurve3;
    line: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial>;
    geo: THREE.BufferGeometry;
    seed: number;
  }[] = [];
  A.forEach((a, i) => {
    PORTS.forEach((p, k) => {
      const serves =
        k === 0 ? i % 2 === 0 : k === 1 ? i % 2 === 1 : k === 2 ? i % 4 === 0 : i % 5 === 2;
      if (!serves) {
        return;
      }
      const mid = new THREE.Vector3((p.x + a.x) / 2, 0.9 + (i % 3) * 0.15, (p.z + a.z) / 2);
      const curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(p.x, 0, p.z),
        mid,
        new THREE.Vector3(a.x, 0.02, a.z),
      );
      const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(48));
      const line = new THREE.Line(geo, lineMat(C.line2, 0));
      scene.add(line);
      curves.push({ curve, line, geo, seed: rnd() });
    });
  });
  const pkGeo = new THREE.BufferGeometry();
  const pkPos = new Float32Array(curves.length * 3);
  pkGeo.setAttribute("position", new THREE.BufferAttribute(pkPos, 3));
  const pkMat = new THREE.PointsMaterial({
    size: 0.11,
    map: dotTex,
    color: C.text,
    transparent: true,
    alphaTest: 0.4,
    depthWrite: false,
    opacity: 0,
  });
  scene.add(new THREE.Points(pkGeo, pkMat));
  const pkGlow = glowMat(C.ink.clone().lerp(C.text, 0.6), 0.62);
  scene.add(new THREE.Points(pkGeo, pkGlow));
  const portMarks = PORTS.map((p) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(0.34, 0.34), basic(C.text2, 0));
    m.rotation.x = -Math.PI / 2;
    m.position.set(p.x, 0, p.z);
    scene.add(m);
    return m;
  });

  // Documents: thin sheets stacked above each account
  const sheetGeo = new THREE.BoxGeometry(0.46, 0.014, 0.32);
  const sheetEdge = new THREE.EdgesGeometry(sheetGeo);
  const sheets = A.flatMap((a) =>
    Array.from({ length: a.docs }, (_, j) => {
      const fill = new THREE.Mesh(sheetGeo, basic(C.fill, 0));
      const edge = new THREE.LineSegments(sheetEdge, lineMat(C.line2, 0));
      const g = new THREE.Group();
      g.add(fill, edge);
      g.rotation.y = -a.ang + (rnd() - 0.5) * 0.25;
      scene.add(g);
      return {
        a,
        j,
        g,
        fill,
        edge,
        y: 0.1 + j * 0.085,
        rel: a.rel.includes(j),
        delay: (a.i / A.length) * 0.45 + (j / a.docs) * 0.3,
      };
    }),
  );
  const liftSheet = need(
    sheets.find((s) => s.a.i === DHL && s.j === 8),
    "DHL Group's quoted document",
  );

  // The sieve: a silicon wafer whose dies are LeadRadar's architecture and flows in miniature. Ticks
  // to or from a model are orange.
  const RW = R + 0.25;
  const B = RW * 2 + 0.4;
  const PITCH = 1.65;
  const DIE = 1.55;
  type Cell = {
    cx: number;
    cz: number;
    full: boolean;
    d: number;
    kind?: "arch" | "flow" | "test";
    flow?: (typeof FLOWS)[number];
  };
  const cells: Cell[] = [];
  for (let gz = -4; gz < 4; gz++) {
    for (let gx = -4; gx < 4; gx++) {
      const cx = (gx + 0.5) * PITCH;
      const cz = (gz + 0.5) * PITCH;
      const far = Math.hypot(Math.abs(cx) + DIE / 2, Math.abs(cz) + DIE / 2);
      const near = Math.hypot(
        Math.max(0, Math.abs(cx) - DIE / 2),
        Math.max(0, Math.abs(cz) - DIE / 2),
      );
      if (near < RW) {
        cells.push({ cx, cz, full: far <= 5.2, d: Math.hypot(cx, cz) });
      }
    }
  }
  const full = cells.filter((c) => c.full);
  const centre = need([...full].sort((p, q) => p.d - q.d)[0], "wafer centre");
  centre.kind = "arch";
  full
    .filter((c) => c !== centre)
    .forEach((c, k) => {
      const flow = FLOWS[k];
      if (flow === undefined) {
        c.kind = "test";
      } else {
        c.kind = "flow";
        c.flow = flow;
      }
    });
  const ARCH: Record<string, [number, number]> = {
    users: [0.08, 0.1],
    web: [0.08, 0.35],
    api: [0.3, 0.52],
    hub: [0.08, 0.82],
    db: [0.55, 0.52],
    worker: [0.8, 0.52],
    emb: [0.55, 0.85],
    llm: [0.82, 0.85],
    src: [0.82, 0.14],
    paid: [0.55, 0.14],
  };
  const ARCH_E: [string, string, boolean][] = [
    ["users", "web", false],
    ["web", "api", false],
    ["api", "db", false],
    ["db", "worker", false],
    ["worker", "llm", true],
    ["api", "llm", true],
    ["worker", "src", false],
    ["worker", "paid", false],
    ["api", "emb", true],
    ["worker", "emb", true],
    ["api", "hub", false],
  ];
  type Pulse = { pts: [number, number][]; hi: boolean; w: [number, number][] };
  const pulses: Pulse[] = [];
  const W1 = {
    wafer: hex(C.page),
    die: hex(C.fill.clone().lerp(C.page, 0.5)),
    dieEdge: hex(C.line),
    hatch: hex(C.fill),
    label: hex(C.line2.clone().lerp(C.grey, 0.3)),
    wire: hex(C.line2),
    node: hex(C.fill),
    nodeEdge: hex(C.grey.clone().lerp(C.page, 0.4)),
    lane: hex(C.line),
    tick: hex(C.line2.clone().lerp(C.grey, 0.3)),
    tickEnd: hex(C.grey.clone().lerp(C.page, 0.3)),
    accent: hex(C.accent),
  };
  const drawBoard = () => {
    const PX = 2048;
    const sc = PX / B;
    const cv = document.createElement("canvas");
    cv.width = cv.height = PX;
    const g = need(cv.getContext("2d"), "2D canvas");
    const X = (x: number) => (x + B / 2) * sc;
    const Z = (z: number) => (z + B / 2) * sc;
    const L = (v: number) => v * sc;
    g.save();
    g.beginPath();
    g.arc(X(0), Z(0), L(RW), 0, TAU);
    g.clip();
    g.globalAlpha = 0.93;
    g.fillStyle = W1.wafer;
    g.fillRect(0, 0, PX, PX);
    g.globalAlpha = 1;
    pulses.length = 0;
    cells.forEach((c) => {
      const x0 = X(c.cx - DIE / 2);
      const z0 = Z(c.cz - DIE / 2);
      const w = L(DIE);
      if (!c.full) {
        g.strokeStyle = W1.dieEdge;
        g.lineWidth = 2;
        g.strokeRect(x0, z0, w, w);
        g.save();
        g.beginPath();
        g.rect(x0, z0, w, w);
        g.clip();
        g.strokeStyle = W1.hatch;
        for (let k = -w; k < w; k += 18) {
          g.beginPath();
          g.moveTo(x0 + k, z0);
          g.lineTo(x0 + k + w, z0 + w);
          g.stroke();
        }
        g.restore();
        return;
      }
      g.fillStyle = W1.die;
      g.fillRect(x0, z0, w, w);
      g.strokeStyle = W1.dieEdge;
      g.lineWidth = 2;
      g.strokeRect(x0, z0, w, w);
      g.fillStyle = W1.label;
      g.font = "500 15px 'Geist Mono', monospace";
      if (c.kind === "test") {
        g.strokeStyle = W1.lane;
        g.beginPath();
        g.moveTo(x0 + w / 2, z0 + 20);
        g.lineTo(x0 + w / 2, z0 + w - 20);
        g.moveTo(x0 + 20, z0 + w / 2);
        g.lineTo(x0 + w - 20, z0 + w / 2);
        g.stroke();
        g.beginPath();
        g.arc(x0 + w / 2, z0 + w / 2, w * 0.18, 0, TAU);
        g.stroke();
        return;
      }
      const m = L(0.1);
      const ix = x0 + m;
      const iz = z0 + L(0.2);
      const iw = w - 2 * m;
      const ih = w - L(0.3);
      if (c.kind === "arch") {
        g.fillText("ARCH", x0 + 8, z0 + 20);
        const P = (k: string): [number, number] => {
          const [ax, az] = need(ARCH[k], k);
          return [ix + ax * iw, iz + az * ih];
        };
        ARCH_E.forEach(([a1, b1, hi]) => {
          const [ax, az] = P(a1);
          const [bx, bz] = P(b1);
          g.strokeStyle = hi ? W1.accent : W1.wire;
          g.lineWidth = 2;
          g.beginPath();
          g.moveTo(ax, az);
          g.lineTo(bx, az);
          g.lineTo(bx, bz);
          g.stroke();
          if (hi) {
            pulses.push({
              pts: [
                [ax, az],
                [bx, az],
                [bx, bz],
              ],
              hi: true,
              w: [],
            });
          }
        });
        Object.keys(ARCH).forEach((k) => {
          const [x, z] = P(k);
          g.fillStyle = k === "llm" ? W1.accent : W1.node;
          g.strokeStyle = k === "llm" ? W1.accent : W1.nodeEdge;
          g.fillRect(x - 11, z - 8, 22, 16);
          g.strokeRect(x - 11, z - 8, 22, 16);
        });
        return;
      }
      const f = need(c.flow, "flow");
      g.fillText(f.id, x0 + 8, z0 + 20);
      const lane = (k: number) => ix + (f.n === 1 ? iw / 2 : (k / (f.n - 1)) * iw);
      g.strokeStyle = W1.lane;
      g.lineWidth = 1.5;
      for (let k = 0; k < f.n; k++) {
        g.beginPath();
        g.moveTo(lane(k), iz - 6);
        g.lineTo(lane(k), iz + ih);
        g.stroke();
        g.fillStyle = W1.lane;
        g.fillRect(lane(k) - 7, iz - 12, 14, 6);
      }
      f.m.forEach(([fa, fb, y, hi], k) => {
        const z = iz + 6 + y * (ih - 12);
        const xa = lane(fa);
        const xb = lane(fb);
        g.strokeStyle = hi ? W1.accent : W1.tick;
        g.lineWidth = hi ? 2.5 : 2;
        g.beginPath();
        g.moveTo(xa, z);
        g.lineTo(xb, z);
        g.stroke();
        g.fillStyle = hi ? W1.accent : W1.tickEnd;
        g.beginPath();
        g.arc(xb, z, 3.2, 0, TAU);
        g.fill();
        if (hi === 1 || k % 5 === 2) {
          pulses.push({
            pts: [
              [xa, z],
              [xb, z],
            ],
            hi: hi === 1,
            w: [],
          });
        }
      });
    });
    g.restore();
    g.strokeStyle = W1.dieEdge;
    g.lineWidth = 3;
    g.beginPath();
    g.arc(X(0), Z(0), L(RW), 0, TAU);
    g.stroke();
    // the wafer notch
    g.globalCompositeOperation = "destination-out";
    g.beginPath();
    g.arc(X(0), Z(-RW), 16, 0, TAU);
    g.fill();
    g.globalCompositeOperation = "source-over";
    // canvas pixels back to world coordinates for the pulses
    pulses.forEach((pl) => (pl.w = pl.pts.map(([x, z]) => [x / sc - B / 2, z / sc - B / 2])));
    const t = new THREE.CanvasTexture(cv);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    return t;
  };
  const sieve = new THREE.Group();
  scene.add(sieve);
  const sieveFill = new THREE.Mesh(
    new THREE.PlaneGeometry(B, B),
    new THREE.MeshBasicMaterial({
      map: drawBoard(),
      transparent: true,
      opacity: 0,
      depthWrite: false,
    }),
  );
  sieveFill.rotation.x = -Math.PI / 2;
  sieve.add(sieveFill);
  const curSets = [false, true].map((hi) => {
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(200 * 3);
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const core = new THREE.PointsMaterial({
      size: hi ? 0.06 : 0.045,
      map: dotTex,
      color: hi ? C.accent : C.text2,
      transparent: true,
      alphaTest: 0.4,
      depthWrite: false,
      opacity: 0,
    });
    const glow = glowMat(hi ? C.accent : C.text, hi ? 0.42 : 0.26);
    sieve.add(new THREE.Points(geo, core), new THREE.Points(geo, glow));
    return { hi, geo, pos, core, glow };
  });
  let disposed = false;
  void document.fonts.ready.then(() => {
    if (!disposed) {
      sieveFill.material.map?.dispose();
      sieveFill.material.map = drawBoard();
      sieveFill.material.needsUpdate = true;
    }
  });
  let time = 0;
  const stepCurrent = (vis: number) => {
    curSets.forEach((cs) => {
      const list = pulses.filter((q) => q.hi === cs.hi).slice(0, 200);
      list.forEach((q, k) => {
        const offset = (k * 0.618) % 1;
        const tt = (time * (cs.hi ? 0.9 : 0.6) + offset) % 1;
        const n = q.w.length - 1;
        const sgi = Math.min(n - 1, Math.floor(tt * n));
        const f = tt * n - sgi;
        const [ax, az] = need(q.w[sgi], "pulse point");
        const [bx, bz] = need(q.w[sgi + 1], "pulse point");
        cs.pos.set([lerp(ax, bx, f), 0.012, lerp(az, bz, f)], k * 3);
      });
      cs.geo.setDrawRange(0, list.length);
      need(cs.geo.attributes["position"], "position").needsUpdate = true;
      cs.core.opacity = vis;
      cs.glow.opacity = vis * (cs.hi ? 0.9 : 0.5);
    });
  };

  // DHL Group's score as a stack of rule segments: Fit on the left, Intent on the right
  const U = 0.028;
  const COL = 0.34;
  const boxGeo = new THREE.BoxGeometry(COL, 1, COL);
  boxGeo.translate(0, 0.5, 0);
  const boxEdge = new THREE.EdgesGeometry(boxGeo);
  const colX = [dA.x - 0.24, dA.x + 0.24] as const;
  const acc = [0, 0];
  const rulesEl = part("rules");
  const SEGS = RULES.map((rule) => {
    const base = acc[rule.col] ?? 0;
    const h = rule.pts * U;
    acc[rule.col] = base + h;
    const g = new THREE.Group();
    g.position.set(colX[rule.col], base, dA.z);
    const fill = new THREE.Mesh(boxGeo, basic(rule.col ? C.accent : C.fill2, 0));
    const edge =
      rule.unknown === true
        ? new THREE.LineSegments(
            boxEdge,
            new THREE.LineDashedMaterial({
              color: C.grey,
              dashSize: 0.04,
              gapSize: 0.035,
              transparent: true,
              opacity: 0,
              depthWrite: false,
            }),
          )
        : new THREE.LineSegments(boxEdge, lineMat(rule.col ? C.accent : C.text2, 0));
    g.add(edge);
    if (rule.unknown !== true) {
      g.add(fill);
    }
    g.scale.set(1, h - 0.012, 1);
    scene.add(g);
    if (rule.unknown === true) {
      edge.computeLineDistances();
    }
    const el = document.createElement("div");
    el.className = `lr-rule${rule.col ? " lr-int" : " lr-left"}${rule.unknown === true ? " lr-unk" : ""}`;
    el.innerHTML = `<b>${rule.label}</b><span>${rule.val}</span>${rule.txt ? `<em>${rule.txt}</em>` : ""}`;
    rulesEl.appendChild(el);
    return { ...rule, base, h, g, fill, edge, el };
  });
  const prioY = DHL_SCORES.priority * U;
  const prioLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-0.5, 0, 0),
      new THREE.Vector3(0.5, 0, 0),
    ]),
    lineMat(C.accent, 0),
  );
  prioLine.position.set(dA.x, prioY, dA.z);
  scene.add(prioLine);

  // One Priority column per account for the ranking
  const BAND: Record<SceneBand, [THREE.Color, THREE.Color]> = {
    hot: [C.accent, C.accent],
    warm: [tone("accent-soft").lerp(C.accent, 0.12), C.ink],
    cold: [tone("cool-soft").lerp(tone("cool"), 0.08), tone("cool")],
  };
  const columns = A.map((a) => {
    const [fc, ec] = a.band === null ? [C.fill2, C.line2] : BAND[a.band];
    const cfill = new THREE.Mesh(boxGeo, basic(fc, 0));
    const cedge = new THREE.LineSegments(boxEdge, lineMat(ec, 0));
    const col = new THREE.Group();
    col.add(cfill, cedge);
    col.scale.set(0.8, 0.001, 0.8);
    scene.add(col);
    a.skyX = -1.15 + a.rankIdx * 0.37;
    return { cfill, cedge, col };
  });

  // HTML labels
  const namesEl = part("names");
  const names = A.map((a) => {
    const el = document.createElement("div");
    el.className = "lr-nm";
    el.textContent = a.n;
    namesEl.appendChild(el);
    return el;
  });
  const portsEl = part("ports");
  const portLabels = PORTS.map((p) => {
    const el = document.createElement("div");
    el.className = "lr-port";
    el.textContent = p.name;
    portsEl.appendChild(el);
    return el;
  });

  let W = 1;
  let H = 1;
  let narrow = false;
  const resize = () => {
    W = stage.clientWidth;
    H = stage.clientHeight;
    narrow = W < 900;
    renderer.setSize(W, H, false);
    camera.aspect = W / H;
    camera.fov = narrow ? 58 : 38;
    camera.updateProjectionMatrix();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(stage);
  resize();

  const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
  const camKeys = () => {
    const o = narrow ? 0 : 1;
    const dl = V(dA.x - 1.1 * o, 1.3, dA.z);
    const shift = narrow ? 2.4 : 0;
    return [
      { p: V(-2.6 * o, 12.2, 10.2), l: V(-2.9 * o, 0, narrow ? 1.8 : 0.2) },
      { p: V(-1.7 * o, 5.9, 12.6), l: V(-2.0 * o, 0.8, 0) },
      { p: dl.clone().add(V(0.4 * o, 1.9, 7.2)), l: dl },
      { p: V(-0.9 * o + shift, 5.2, 13.5), l: V(-1.1 * o + shift, 1.1, 0) },
      { p: V(-1.0 * o + shift, 1.9, 15.5), l: V(-1.0 * o + shift, 1.2, 0) },
    ] as const;
  };
  const tmp = new THREE.Vector3();
  const camP = new THREE.Vector3();
  const camL = new THREE.Vector3();
  const toScreen = (x: number, y: number, z: number): [number, number] => {
    tmp.set(x, y, z).project(camera);
    return [(tmp.x * 0.5 + 0.5) * W, (-tmp.y * 0.5 + 0.5) * H];
  };
  const setPos = (el: HTMLElement, x: number, y: number) => {
    el.style.left = `${String(x)}px`;
    el.style.top = `${String(y)}px`;
  };
  const col = new THREE.Color();

  const card = part("card");
  const trans = part("trans");
  const src = part("src");
  const list = part("list");
  const nFit = part("n-fit");
  const nInt = part("n-int");
  const nPrio = part("n-prio");
  const cntFit = part("cnt-fit");
  const cntInt = part("cnt-int");
  const prioL = part("prio");
  const flyers = [part("fly-0"), part("fly-1")];
  const rows = [part("row-0"), part("row-1")];
  const flySrc = [DHL, LUFTHANSA];
  const relRect = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    const s = stage.getBoundingClientRect();
    return { x: r.left - s.left, y: r.top - s.top };
  };
  const progress = () => {
    const r = scroll.getBoundingClientRect();
    const range = r.height - innerHeight;
    return range > 0 ? clamp(-r.top / range) : 0;
  };
  const caret = document.createElement("span");
  caret.className = "lr-caret";
  const typed = document.createTextNode("");
  trans.append(typed);

  let last = performance.now();
  let lastP = -1;
  let raf = 0;
  const frame = (now: number) => {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!reduced) {
      time += dt;
    }
    const p = progress();
    if (reduced && p === lastP) {
      return;
    }
    lastP = p;
    const step = Math.round(p * (steps - 1));
    tl.seek(reduced ? step * 1000 : p * TOTAL);

    // camera: accounts, then lower for the documents, then close on DHL Group, then the skyline, then face-on
    const K = camKeys();
    camP.copy(K[0].p);
    camL.copy(K[0].l);
    (
      [
        [K[1], S.tilt],
        [K[2], S.focus],
        [K[3], S.unfocus],
        [K[4], S.flat],
      ] as const
    ).forEach(([key, t]) => {
      const e = ease(t);
      camP.lerp(key.p, e);
      camL.lerp(key.l, e);
    });
    camera.position.copy(camP);
    camera.lookAt(camL);

    const away = Math.max(S.focus * (1 - S.unfocus), 0);
    const sceneOut = S.flat;
    floorMat.opacity =
      (1 - 0.5 * away) *
      (1 - clamp(S.sift * 6) * (1 - S.focus) * 0.8) *
      (1 - S.sort * 0.6) *
      (1 - sceneOut);
    floor.visible = floorMat.opacity > 0.004;
    discMats.forEach(([m, o]) => {
      m.opacity = o * (1 - 0.6 * away) * (1 - S.sort * 0.85) * (1 - sceneOut);
    });

    // points
    A.forEach((_, i) => {
      col.copy(C.grey).lerp(C.text, S.src * 0.35);
      if (i === DHL && S.focus > 0.02) {
        col.lerp(C.accent, S.focus);
      }
      col.multiplyScalar(i === DHL ? 1 : 1 - 0.75 * away);
      ptCol.set([col.r, col.g, col.b], i * 3);
    });
    need(ptGeo.attributes["color"], "color").needsUpdate = true;
    points.material.opacity = 1 - S.rise;
    points.visible = S.rise < 0.99;

    // sources
    const srcVis = 1 - S.read * 0.85;
    curves.forEach((c, k) => {
      const local = clamp(S.src * 1.6 - c.seed * 0.6);
      c.geo.setDrawRange(0, Math.floor(local * 49));
      c.line.material.opacity = 0.55 * srcVis * (1 - S.sift);
      const t = local >= 1 ? (time * 0.28 + c.seed) % 1 : local;
      const pt = c.curve.getPoint(reduced ? 0.6 : t);
      pkPos.set([pt.x, pt.y, pt.z], k * 3);
    });
    need(pkGeo.attributes["position"], "position").needsUpdate = true;
    pkMat.opacity = clamp(S.src * 2 - 1) * (1 - S.read);
    pkGlow.opacity = pkMat.opacity * 0.95;
    portMarks.forEach((m) => {
      m.material.opacity = S.src * (1 - S.sift) * 0.9;
      m.visible = m.material.opacity > 0.004;
    });

    // documents: fall into stacks, then the sieve sets most of them aside
    const sieveY = lerp(1.7, -0.06, S.sift);
    sieve.position.y = sieveY;
    const sv = clamp(S.sift * 6) * (1 - S.focus);
    sieveFill.material.opacity = 0.9 * sv;
    sieve.visible = sv > 0.004;
    if (sieve.visible) {
      stepCurrent(sv);
    }
    sheets.forEach((sh) => {
      const a = sh.a;
      const l = ease(clamp((S.read - sh.delay) / 0.25));
      let y = lerp(sh.y + 2.2, sh.y, l);
      let op = l;
      let edgeC = C.line2;
      const passed = clamp((sh.y - sieveY) / 0.3) * (S.sift > 0 ? 1 : 0);
      if (!sh.rel) {
        op *= 1 - passed;
        y -= passed * 0.5;
      } else if (passed > 0) {
        edgeC = a.i === DHL ? C.accent : C.text2;
      }
      op *= a.i === DHL ? 1 - S.docsOut : 1 - 0.75 * away;
      op *= 1 - S.collapse;
      if (sh === liftSheet) {
        const e = ease(S.lift);
        y += e * 1.1;
        sh.g.rotation.x = -e * 0.9;
        op *= 1 - clamp(S.card * 1.4);
      }
      sh.g.position.set(a.x, y, a.z);
      sh.fill.material.opacity = op * 0.95;
      sh.edge.material.opacity = op;
      sh.edge.material.color.copy(edgeC);
      sh.g.visible = op > 0.004;
    });

    // quote card grows out of the lifted sheet
    const [sx, sy] = toScreen(
      liftSheet.g.position.x,
      liftSheet.g.position.y,
      liftSheet.g.position.z,
    );
    const cardL = narrow ? 16 : Math.min(W - 460, W * 0.58);
    const cardT = narrow ? 76 : H * 0.2;
    const ce = ease(S.card);
    setPos(card, cardL, cardT);
    card.style.transform = `translate(${String((sx - cardL) * (1 - ce))}px, ${String((sy - cardT) * (1 - ce))}px) scale(${String(lerp(0.12, 1, ce))})`;
    card.style.opacity = String(clamp(S.card * 3) * (1 - S.quoteOut));
    typed.data = TRANSLATION.slice(0, Math.round(S.typeT * TRANSLATION.length));
    if (S.typeT > 0 && S.typeT < 1) {
      trans.append(caret);
    } else {
      caret.remove();
    }
    src.style.opacity = S.typeT > 0.95 ? "1" : "0";

    // DHL Group's rule stack
    SEGS.forEach((sg, k) => {
      const e = clamp(S[`g${String(k)}` as Key]);
      sg.g.position.y = sg.base + (1 - e) * 1.0;
      const op = e * (1 - S.collapse);
      sg.fill.material.opacity = op * (sg.col ? 0.92 : 0.9);
      sg.edge.material.opacity = op;
      sg.g.visible = op > 0.004;
      const [lx, ly] = toScreen(colX[sg.col] + (sg.col ? 0.26 : -0.26), sg.base + sg.h / 2, dA.z);
      setPos(sg.el, lx, ly);
      sg.el.style.opacity = String(op);
    });
    const [fx, fy] = toScreen(colX[0], -0.08, dA.z + 0.2);
    const [ix, iy] = toScreen(colX[1], -0.08, dA.z + 0.2);
    setPos(cntFit, fx, fy);
    setPos(cntInt, ix, iy);
    cntFit.style.opacity = cntInt.style.opacity = String(clamp(S.g0 * 2) * (1 - S.collapse));
    nFit.textContent = String(Math.round(DHL_SCORES.fit * S.fitN));
    nInt.textContent = String(Math.round(DHL_SCORES.intent * S.intN));
    prioLine.scale.x = Math.max(S.prioLine, 0.001);
    prioLine.material.opacity = S.prioLine * (1 - S.collapse);
    const [px, py] = toScreen(dA.x + 0.5, prioY, dA.z);
    setPos(prioL, px, py);
    prioL.style.opacity = String(S.prioLine * (1 - S.collapse));
    nPrio.textContent = String(Math.round(DHL_SCORES.priority * S.prioLine));

    // the ranking: every account rises to its Priority, then the columns line up
    const se = ease(S.sort);
    A.forEach((a, i) => {
      const c = need(columns[i], "column");
      const h = Math.max(0.001, a.prio * U * ease(S.rise) * (1 - sceneOut * 0.97));
      c.col.position.set(lerp(a.x, a.skyX, se), 0, lerp(a.z, 0, se));
      c.col.scale.set(lerp(0.8, 0.85, se), h, lerp(0.8, 0.85, se));
      const op = clamp(S.rise * 3) * (1 - sceneOut * 0.85);
      c.cfill.material.opacity = op * (a.band === null ? 0.8 : 0.95);
      c.cedge.material.opacity = op;
      c.col.visible = op > 0.004;
    });

    // names: all at first, then only DHL Group, then the leader on its column
    A.forEach((a, i) => {
      const el = need(names[i], "name");
      const c = need(columns[i], "column");
      const top = S.rise > 0.01;
      const leads = a.rankIdx < 1;
      const [x, y] = top
        ? toScreen(c.col.position.x, a.prio * U * ease(S.rise) + 0.18, c.col.position.z)
        : toScreen(a.x, 0, a.z);
      a.sx = x;
      a.sy = y;
      let op = (1 - S.src * 0.45) * (1 - 0.9 * away);
      op *= 1 - clamp(S.sift * 6) * (1 - S.focus) * (a.rel.length ? 0.35 : 0.92);
      if (i === DHL) {
        op = Math.max(op, S.focus * (1 - S.collapse) * (1 - clamp(S.g0 * 2)));
      }
      if (top) {
        op = leads ? clamp(S.rise * 2) * (1 - S.fly) : op * (1 - clamp(S.rise * 3));
      }
      el.style.transform = top && leads ? "translate(-50%, -100%)" : "";
      el.classList.toggle("lr-on", top && leads);
      el.classList.toggle("lr-focus", i === DHL && S.focus > 0.5 && !top);
      setPos(el, x, y);
      el.style.opacity = String(op);
    });
    PORTS.forEach((pt, k) => {
      const el = need(portLabels[k], "source label");
      const [x, y] = toScreen(pt.x, 0, pt.z);
      setPos(el, x, y);
      el.style.opacity = String(S.src * (1 - S.sift));
    });

    // the list takes over; the leaders' names fly into their rows
    const lw = narrow ? W - 32 : Math.min(760, W * 0.54);
    const ll = narrow ? 16 : W - lw - 72;
    list.style.width = `${String(lw)}px`;
    setPos(list, ll, narrow ? 76 : H * 0.18);
    list.style.opacity = String(S.list);
    list.style.transform = `translateY(${String((1 - S.list) * 14)}px)`;
    flyers.forEach((f, k) => {
      const a = need(A[need(flySrc[k], "flyer")], "flyer account");
      const row = need(rows[k], "row");
      const fk = ease(clamp((S.fly - k * 0.2) / 0.8));
      const tr = relRect(row);
      setPos(f, lerp(a.sx - f.offsetWidth / 2, tr.x, fk), lerp(a.sy - 14, tr.y, fk));
      f.style.opacity = S.fly > 0 && fk < 0.999 ? "1" : "0";
      row.style.opacity = S.fly === 0 ? "0" : fk >= 0.999 ? "1" : "0";
    });

    renderer.render(scene, camera);
  };
  raf = requestAnimationFrame(frame);

  return () => {
    disposed = true;
    cancelAnimationFrame(raf);
    observer.disconnect();
    scene.traverse((o) => {
      if (o instanceof THREE.Mesh || o instanceof THREE.Line || o instanceof THREE.Points) {
        (o.geometry as THREE.BufferGeometry).dispose();
        const m = o.material as THREE.Material & { map?: THREE.Texture | null };
        m.map?.dispose();
        m.dispose();
      }
    });
    renderer.dispose();
    overlay.innerHTML = "";
  };
}
