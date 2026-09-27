import "@testing-library/jest-dom/vitest";
import "vitest-axe/extend-expect";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";

import {
  installCanvasStub,
  installMatchMedia,
  installPointerStubs,
  setReducedMotion,
} from "./testEnvironment";
import { server } from "./testServer";

expect.extend(axeMatchers);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
beforeEach(() => {
  setReducedMotion(false);
  installMatchMedia();
  installPointerStubs();
  installCanvasStub();
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});
