import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router";

import { App } from "./App";

describe("App", () => {
  it("mounts without error", () => {
    expect(() =>
      render(
        <MemoryRouter>
          <App />
        </MemoryRouter>,
      ),
    ).not.toThrow();
  });
});
