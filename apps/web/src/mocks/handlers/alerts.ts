import { http, HttpResponse } from "msw";
import type { components } from "../../api/schema.gen";

// PLACEHOLDER(wireframe): replace the unread count when alert fixtures are recorded.
const unreadAlerts: components["schemas"]["Page_AlertView_"] = {
  items: [],
  page: 1,
  page_size: 25,
  total: 3,
};
export const alertHandlers = [http.get("*/api/v1/alerts", () => HttpResponse.json(unreadAlerts))];
