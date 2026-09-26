// The mock of the pending contracts API-07, API-15, API-16, API-23, API-39 to API-45, API-71 and
// API-74. Temporary: `API-39` filters only by exact `standing` and `band`, the
// fixture order is the ranking, and `API-44` and `API-45` change the override list and nothing else.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse, olgaAdmin } from "../authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../contract";
import {
  accounts,
  evidenceFor,
  findings,
  industries,
  markets,
  prospectRows,
  scoreViews,
  scoringConfig,
  scoringSummaries,
  services,
} from "./prospectsAndEvidence.fixtures";

const FIXTURE_SERVICE = "svc-1";

export function createProspectsHandlers() {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const overrideRows: Schemas["Override"][] = [];
  let nextOverrideId = 1;
  const notFound = errorEnvelope("NOT_FOUND", "Not found.");

  return [
    http.get("/api/v1/services", ({ response }) => response(200).json(services)),
    http.get("/api/v1/industries", ({ response }) => response(200).json(industries)),
    http.get("/api/v1/markets", ({ response }) => response(200).json(markets)),
    http.get("/api/v1/services/{id}/scoring-configs", ({ params, response }) =>
      response(200).json(params.id === FIXTURE_SERVICE ? scoringSummaries : []),
    ),
    http.get("/api/v1/scoring-configs/{id}", ({ params, response }) =>
      params.id === scoringConfig.id
        ? response(200).json(scoringConfig)
        : errorResponse(notFound, 404),
    ),
    http.get("/api/v1/accounts/{id}", ({ params, response }) => {
      const found = accounts.find((candidate) => candidate.id === params.id);
      return found === undefined ? errorResponse(notFound, 404) : response(200).json(found);
    }),
    http.get("/api/v1/services/{id}/prospects", ({ request, response }) => {
      const query = new URL(request.url).searchParams;
      const standing = query.get("standing") ?? "RANKED";
      const band = query.get("band");
      const items = prospectRows.filter(
        (item) => item.standing === standing && (band === null || item.band === band),
      );
      const ranked = prospectRows.filter((item) => item.standing === "RANKED");
      const count = (name: string) => ranked.filter((item) => item.band === name).length;
      return response(200).json({
        items,
        page: 1,
        page_size: 25,
        total: items.length,
        band_counts: { HOT: count("HOT"), WARM: count("WARM"), COLD: count("COLD") },
      });
    }),
    http.get("/api/v1/accounts/{id}/scores/{service_id}", ({ params, response }) => {
      const found = scoreViews.find((candidate) => candidate.account_id === params.id);
      return found === undefined
        ? errorResponse(notFound, 404)
        : response(200).json({ ...found, overrides: overrideRows });
    }),
    http.get("/api/v1/accounts/{id}/findings", ({ params, request, response }) => {
      const status = new URL(request.url).searchParams.get("status") ?? "ACTIVE";
      return response(200).json(
        findings.filter(
          (candidate) => candidate.account_id === params.id && candidate.status === status,
        ),
      );
    }),
    http.get("/api/v1/findings/{id}/evidence", ({ params, response }) => {
      const evidence = evidenceFor(params.id);
      return evidence === undefined ? errorResponse(notFound, 404) : response(200).json(evidence);
    }),
    http.post(
      "/api/v1/accounts/{id}/scores/{service_id}/overrides",
      async ({ params, request, response }) => {
        const body = await request.json();
        if (overrideRows.some((row) => row.rule_key === body.rule_key && row.status === "ACTIVE")) {
          return errorResponse(
            errorEnvelope("CONFLICT", "An exception is already active for this rule."),
            409,
          );
        }
        const created: Schemas["Override"] = {
          id: `ovr-${String(nextOverrideId++)}`,
          account_id: params.id,
          service_id: params.service_id,
          rule_key: body.rule_key,
          note: body.note,
          rule_label: "Outside DACH",
          status: "ACTIVE",
          created_by_name: olgaAdmin.display_name,
          created_at: "2026-09-26T09:00:00Z",
          revoked_by_name: null,
          revoked_at: null,
          run_id: "run-rescore",
        };
        overrideRows.push(created);
        return response(200).json(created);
      },
    ),
    http.post("/api/v1/overrides/{id}/revoke", ({ params, response }) => {
      const index = overrideRows.findIndex((candidate) => candidate.id === params.id);
      const current = overrideRows[index];
      if (current === undefined) {
        return errorResponse(notFound, 404);
      }
      const revoked: Schemas["Override"] = {
        ...current,
        status: "REVOKED",
        revoked_by_name: olgaAdmin.display_name,
        revoked_at: "2026-09-26T10:00:00Z",
      };
      overrideRows[index] = revoked;
      return response(200).json(revoked);
    }),
  ];
}
