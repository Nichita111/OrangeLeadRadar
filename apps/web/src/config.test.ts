import { HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { loadConfig, parseConfig } from "./config";
import { http, server } from "./testServer";

const FULL_BODY = {
  CONFIDENCE_HIGH_MIN: "0.85",
  CONFIDENCE_MEDIUM_MIN: "0.65",
  RUN_POLL_INTERVAL_MS: "2000",
};

describe("config.json (frontend Design, P-10)", () => {
  it("parses into a typed Config", () => {
    expect(parseConfig(FULL_BODY)).toEqual({
      CONFIDENCE_HIGH_MIN: 0.85,
      CONFIDENCE_MEDIUM_MIN: 0.65,
      RUN_POLL_INTERVAL_MS: 2000,
    });
  });

  it.each(["CONFIDENCE_HIGH_MIN", "CONFIDENCE_MEDIUM_MIN", "RUN_POLL_INTERVAL_MS"])(
    "throws naming %s when it is missing, with no default",
    (missing) => {
      const partial = Object.fromEntries(
        Object.entries(FULL_BODY).filter(([key]) => key !== missing),
      );
      expect(() => parseConfig(partial)).toThrow(new RegExp(missing));
    },
  );

  it.each(["abc", "", "1.5", "-0.1", "NaN"])("throws on the bad value %j", (value) => {
    expect(() => parseConfig({ ...FULL_BODY, CONFIDENCE_HIGH_MIN: value })).toThrow(
      /CONFIDENCE_HIGH_MIN/,
    );
  });

  it.each(["0", "-1", "1.5", "abc", ""])(
    "throws when RUN_POLL_INTERVAL_MS is not a positive integer (%j)",
    (value) => {
      expect(() => parseConfig({ ...FULL_BODY, RUN_POLL_INTERVAL_MS: value })).toThrow(
        /RUN_POLL_INTERVAL_MS/,
      );
    },
  );

  it("throws when the body is not an object", () => {
    expect(() => parseConfig("nope")).toThrow(/config\.json/);
  });

  it("loads /config.json", async () => {
    server.use(
      http.untyped.get(`${window.location.origin}/config.json`, () => HttpResponse.json(FULL_BODY)),
    );
    await expect(loadConfig()).resolves.toEqual({
      CONFIDENCE_HIGH_MIN: 0.85,
      CONFIDENCE_MEDIUM_MIN: 0.65,
      RUN_POLL_INTERVAL_MS: 2000,
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
