import anime from "animejs";
import * as THREE from "three";

import {
  R,
  SEC,
  buildDisc,
  buildFloor,
  disposeScene,
  dotPoints,
  layoutAccounts,
  readTones,
  seededRandom,
  spriteTextures,
} from "../../landing/radar";

/**
 * The Accept invite scene (FR-172): the Landing floor, disc and accounts seen as Landing's first
 * step sees them, and the invitee as one more point. It draws only when something changes; the
 * beam's one sweep on success is its only motion ([ADR-21](
 * /architecture/adrs/adr-21-invite-links-and-the-invite-scene.md)).
 */
export interface InviteScene {
  /** Shows the display name as the new point's label; an empty name hides the point. */
  setName: (name: string) => void;
  /** Sweeps the beam over the new point and turns it Accent; resolves when done. */
  celebrate: () => Promise<void>;
  dispose: () => void;
}

// The new point sits in the widest gap of the disc, the sector with one account.
const YOU_ANGLE = 2 * SEC + 0.72 * SEC;
const YOU_RADIUS = 4.3;
const SWEEP_MS = 1100;

/** Mounts the scene; answers null when the browser has no WebGL (FR-173). */
export function mountInviteScene(targets: {
  stage: HTMLElement;
  canvas: HTMLCanvasElement;
  overlay: HTMLElement;
  reduced: boolean;
}): InviteScene | null {
  const { stage, canvas, overlay, reduced } = targets;
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch {
    return null;
  }
  const C = readTones();
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(C.page, 1);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120);
  camera.position.set(-2.6, 12.2, 10.2);
  camera.lookAt(-2.9, 0, 0.2);

  scene.add(buildFloor(C).floor);
  scene.add(buildDisc(C).disc);
  const { dotTex, glowTex } = spriteTextures(C);

  const accounts = layoutAccounts(seededRandom(5));
  const positions = new Float32Array(accounts.length * 3);
  const colours = new Float32Array(accounts.length * 3);
  const dim = C.grey.clone().lerp(C.page, 0.35);
  accounts.forEach((a, i) => {
    positions.set([a.x, 0.01, a.z], i * 3);
    colours.set([dim.r, dim.g, dim.b], i * 3);
  });
  scene.add(dotPoints(positions, colours, dotTex));

  const youX = Math.cos(YOU_ANGLE) * YOU_RADIUS;
  const youZ = Math.sin(YOU_ANGLE) * YOU_RADIUS;
  const youColour = new Float32Array([C.text.r, C.text.g, C.text.b]);
  const you = dotPoints(new Float32Array([youX, 0.012, youZ]), youColour, dotTex);
  you.material.size = 0.26;
  you.visible = false;
  scene.add(you);
  const glow = new THREE.Points(
    you.geometry,
    new THREE.PointsMaterial({
      size: 1.1,
      map: glowTex,
      color: C.accent,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      opacity: 0,
    }),
  );
  scene.add(glow);

  // The beam: a thin Accent wedge from the centre, swept once around the disc.
  const beam = new THREE.Mesh(
    new THREE.CircleGeometry(R, 48, 0, SEC * 0.22),
    new THREE.MeshBasicMaterial({
      color: C.accent,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  beam.rotation.x = -Math.PI / 2;
  beam.position.y = 0.005;
  scene.add(beam);

  const names = accounts.map((a) => {
    const el = document.createElement("div");
    el.className = "ai-nm";
    el.textContent = a.n;
    overlay.appendChild(el);
    return { el, x: a.x, z: a.z };
  });
  const youLabel = document.createElement("div");
  youLabel.className = "ai-nm ai-you";
  overlay.appendChild(youLabel);

  let width = 1;
  let height = 1;
  const project = (el: HTMLElement, x: number, z: number) => {
    const p = new THREE.Vector3(x, 0, z).project(camera);
    el.style.left = `${String((p.x * 0.5 + 0.5) * width)}px`;
    el.style.top = `${String((-p.y * 0.5 + 0.5) * height)}px`;
  };
  const draw = () => {
    names.forEach(({ el, x, z }) => {
      project(el, x, z);
    });
    project(youLabel, youX, youZ);
    renderer.render(scene, camera);
  };
  const resize = () => {
    width = stage.clientWidth;
    height = stage.clientHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    draw();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(stage);
  resize();

  const light = () => {
    youColour.set([C.accent.r, C.accent.g, C.accent.b]);
    const attribute = you.geometry.getAttribute("color");
    attribute.needsUpdate = true;
    glow.material.opacity = 0.9;
    youLabel.classList.add("ai-lit");
  };

  let sweep: anime.AnimeInstance | null = null;
  return {
    setName: (name) => {
      you.visible = name.trim() !== "";
      youLabel.textContent = name.trim();
      draw();
    },
    celebrate: () => {
      if (reduced) {
        light();
        draw();
        return Promise.resolve();
      }
      // The wedge starts a quarter turn before the new point and passes it once.
      const state = { angle: YOU_ANGLE - Math.PI / 2 };
      let lit = false;
      sweep = anime({
        targets: state,
        angle: YOU_ANGLE + Math.PI / 3,
        duration: SWEEP_MS,
        easing: "easeInOutSine",
        update: (animation) => {
          beam.rotation.z = -state.angle;
          // Full strength while it sweeps, fading out over its last stretch.
          beam.material.opacity = 0.28 * (1 - (animation.progress / 100) ** 4);
          if (!lit && state.angle >= YOU_ANGLE) {
            lit = true;
            light();
          }
          draw();
        },
      });
      return sweep.finished.then(() => {
        beam.material.opacity = 0;
        draw();
      });
    },
    dispose: () => {
      sweep?.pause();
      observer.disconnect();
      disposeScene(scene, renderer);
      overlay.replaceChildren();
    },
  };
}
