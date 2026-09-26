import { HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { loadConfig, parseConfig } from "./config";
import { http, server } from "./testServer";

describe("config.json (frontend Design, P-10)", () => {
  it("parses into a typed Config", () => {
    expect(parseConfig({ CONFIDENCE_HIGH_MIN: "0.85", CONFIDENCE_MEDIUM_MIN: "0.65" })).toEqual({
      CONFIDENCE_HIGH_MIN: 0.85,
      CONFIDENCE_MEDIUM_MIN: 0.65,
    });
  });

  it("throws naming a missing key, with no default", () => {
    expect(() => parseConfig({ CONFIDENCE_HIGH_MIN: "0.85" })).toThrow(/CONFIDENCE_MEDIUM_MIN/);
  });

  it.each(["abc", "", "1.5", "-0.1", "NaN"])("throws on the bad value %j", (value) => {
    expect(() =>
      parseConfig({ CONFIDENCE_HIGH_MIN: value, CONFIDENCE_MEDIUM_MIN: "0.65" }),
    ).toThrow(/CONFIDENCE_HIGH_MIN/);
  });

  it("throws when the body is not an object", () => {
    expect(() => parseConfig("nope")).toThrow(/config\.json/);
  });

  it("loads /config.json", async () => {
    server.use(
      http.untyped.get(`${window.location.origin}/config.json`, () =>
        HttpResponse.json({ CONFIDENCE_HIGH_MIN: "0.9", CONFIDENCE_MEDIUM_MIN: "0.5" }),
      ),
    );
    await expect(loadConfig()).resolves.toEqual({
      CONFIDENCE_HIGH_MIN: 0.9,
      CONFIDENCE_MEDIUM_MIN: 0.5,
    });
  });

  it("throws on a failed fetch", async () => {
    server.use(
      http.untyped.get(`${window.location.origin}/config.json`, () =>
        HttpResponse.text("missing", { status: 404 }),
      ),
    );
    await expect(loadConfig()).rejects.toThrow(/404/);
  });
});
