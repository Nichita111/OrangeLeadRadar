import { setupWorker } from "msw/browser";
import { alertHandlers } from "./handlers/alerts";
import { authHandlers } from "./handlers/auth";
import { serviceHandlers } from "./handlers/services";

export const worker = setupWorker(...authHandlers, ...serviceHandlers, ...alertHandlers);
