import { Color } from "ogl";

import { AURORA_AMPLITUDE, AURORA_BLEND } from "./values";

interface AuroraUniformInput {
  /** CSS colour strings read from the Accent, Accent soft and Accent tokens. */
  colorStops: string[];
  /** The Surface token: the shader mixes towards it in light mode. */
  surface: string;
  lightMode: boolean;
}

function toRgb(css: string): [number, number, number] {
  const color = new Color(css);
  return [color.r, color.g, color.b];
}

/** The shader's uniforms, apart from time and resolution, which change per frame. */
export function auroraUniforms({ colorStops, surface, lightMode }: AuroraUniformInput) {
  return {
    uAmplitude: { value: AURORA_AMPLITUDE },
    uColorStops: { value: colorStops.map(toRgb) },
    uSurface: { value: toRgb(surface) },
    uBlend: { value: AURORA_BLEND },
    uLightMode: { value: lightMode ? 1 : 0 },
  };
}
