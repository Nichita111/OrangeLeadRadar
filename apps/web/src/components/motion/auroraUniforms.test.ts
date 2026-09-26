import { describe, expect, it } from "vitest";

import { auroraUniforms } from "./auroraUniforms";

const stops = ["#c2410c", "#fff1e7", "#c2410c"];

describe("auroraUniforms (FR-106, FR-125)", () => {
  it.each([
    ["light", true, 1],
    ["dark", false, 0],
  ])("%s: uSurface is the RGB of the Surface token", (_theme, lightMode, flag) => {
    const uniforms = auroraUniforms({
      colorStops: stops,
      surface: lightMode ? "#ffffff" : "#17171a",
      lightMode,
    });
    const expected = lightMode ? [1, 1, 1] : [0x17 / 255, 0x17 / 255, 0x1a / 255];
    const surface = uniforms.uSurface.value;
    surface.forEach((channel, index) => {
      expect(channel).toBeCloseTo(expected[index] ?? NaN, 5);
    });
    expect(uniforms.uLightMode.value).toBe(flag);
  });

  it("the colour stops are those of the three given tokens", () => {
    const uniforms = auroraUniforms({ colorStops: stops, surface: "#ffffff", lightMode: true });
    const rgb = uniforms.uColorStops.value;
    expect(rgb).toHaveLength(3);
    expect(rgb[0]?.[0]).toBeCloseTo(0xc2 / 255, 5);
    expect(rgb[1]?.[2]).toBeCloseTo(0xe7 / 255, 5);
    expect(rgb[2]).toEqual(rgb[0]);
  });
});
