import { createOpenApiHttp } from "openapi-msw";
import { setupServer } from "msw/node";

import type { paths } from "./api/contract";

/** Typed handlers: a path, status or body the contract does not declare fails to compile. */
export const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });

/** The in-process MSW server of the tests; each test arranges its own responses. */
export const server = setupServer(
  // The shell reads the services for its selector on every signed-in screen.
  http.get("/api/v1/services", ({ response }) => response(200).json([])),
);
