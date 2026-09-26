import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("mounts without error", () => {
    expect(() => render(<App />)).not.toThrow();
  });
});
