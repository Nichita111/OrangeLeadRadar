// The development mock of alerts (`API-48`, `API-49`), so Alerts and the unread counts work with
// no api (TypeScript Mock layer). Temporary: the alerts are the fixtures', not raised by scoring.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse } from "../api/authenticationAndUsers.fixtures";
import type { paths } from "../api/contract";
import { mockSessionUser } from "./authentication";
import type { MockStore } from "./store";

/** `PAGE_SIZE_DEFAULT` of the api's runtime. */
const PAGE_SIZE_DEFAULT = 50;

export function createAlertsHandlers(store: MockStore) {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });

  return [
    http.get("/api/v1/alerts", ({ query, response }) => {
      const serviceId = query.get("service_id");
      const unread = query.get("unread") === "true";
      const page = Number(query.get("page") ?? 1);
      const pageSize = Number(query.get("page_size") ?? PAGE_SIZE_DEFAULT);
      const items = store.alerts
        .filter(
          (alert) =>
            (serviceId === null || alert.service.id === serviceId) &&
            (!unread || alert.acknowledged_at === null),
        )
        .sort((left, right) => right.created_at.localeCompare(left.created_at));
      return response(200).json({
        items: items.slice((page - 1) * pageSize, page * pageSize),
        page,
        page_size: pageSize,
        total: items.length,
      });
    }),
    http.post("/api/v1/alerts/{id}/acknowledge", ({ params, response }) => {
      const alert = store.alerts.find((row) => row.id === params.id);
      if (alert === undefined) {
        return errorResponse(errorEnvelope("NOT_FOUND", "Not found."), 404);
      }
      if (alert.acknowledged_at === null) {
        alert.acknowledged_at = new Date().toISOString();
        alert.acknowledged_by_name = mockSessionUser().display_name;
      }
      return response(200).json(alert);
    }),
  ];
}
