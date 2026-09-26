import { http, HttpResponse } from "msw";
import { services } from "../fixtures/services";

export const serviceHandlers = [http.get("*/api/v1/services", () => HttpResponse.json(services))];
