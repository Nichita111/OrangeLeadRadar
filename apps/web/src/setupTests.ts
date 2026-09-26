import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";

import {
  installCanvasStub,
  installMatchMedia,
  installPointerStubs,
  setReducedMotion,
} from "./testEnvironment";
import { server } from "./testServer";

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
