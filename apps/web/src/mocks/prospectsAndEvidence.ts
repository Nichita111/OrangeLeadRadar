// The development mock of the Prospects and evidence screens' contracts (TypeScript Mock layer).
// Temporary: the fixtures stand for every service, so the service id is not read; an override
// re-derives standing and band from the disqualifiers and the active settings' thresholds without
// rescoring; findings are ordered by the size of their points, then `observed_at`; and
// `last_refreshed` sorts newest first.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse, olgaAdmin } from "../api/authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../api/contract";
import {
  accounts,
  evidenceFor,
  findings,
  prospectRows,
  scoreViews,
  scoringConfig,
} from "./prospectsAndEvidence.fixtures";

type Band = Schemas["AccountScoreBand"];
type Override = Schemas["Override"];
type ProspectRow = Schemas["ProspectRow"];
type ScoreView = Schemas["ScoreView"];

/** `PAGE_SIZE_DEFAULT` and `PAGE_SIZE_MAX` of the api's runtime. */
const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_MAX = 200;

const BANDS: Band[] = ["HOT", "WARM", "COLD"];
const { settings } = scoringConfig;
const minFit = Number(settings.min_fit);
const hotThreshold = Number(settings.hot_threshold);
const warmThreshold = Number(settings.warm_threshold);

/** The ranking order of Priority, standing and band. */
function byRanking(left: ProspectRow, right: ProspectRow): number {
  return (
    right.priority - left.priority ||
    right.intent - left.intent ||
    right.fit - left.fit ||
    left.account.name.localeCompare(right.account.name)
  );
}

const sorts: Record<string, (left: ProspectRow, right: ProspectRow) => number> = {
  priority: byRanking,
  intent: (left, right) => right.intent - left.intent || byRanking(left, right),
  fit: (left, right) => right.fit - left.fit || byRanking(left, right),
  name: (left, right) => left.account.name.localeCompare(right.account.name),
  last_refreshed: (left, right) =>
    (right.last_refreshed_at ?? "").localeCompare(left.last_refreshed_at ?? "") ||
    byRanking(left, right),
};

function matchesQuery(row: ProspectRow, q: string): boolean {
  const needle = q.trim().toLowerCase();
  const aliases = accounts.find((account) => account.id === row.account.id)?.aliases ?? [];
  return [row.account.name, row.account.domain, ...aliases].some((value) =>
    value.toLowerCase().includes(needle),
  );
}

function validation(field: string, message: string): Response {
  return errorResponse(
    errorEnvelope("VALIDATION", "The input is invalid.", { fields: [{ field, message }] }),
    422,
  );
}

export function createProspectsHandlers() {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const overrideRows: Override[] = [];
  let nextId = 1;
  const notFound = errorEnvelope("NOT_FOUND", "Not found.");

  function activeOverride(accountId: string, ruleKey: string): Override | undefined {
    return overrideRows.find(
      (row) => row.account_id === accountId && row.rule_key === ruleKey && row.status === "ACTIVE",
    );
  }

  /** The score as the account's active overrides leave it. */
  function currentScore(base: ScoreView): ScoreView {
    const disqualifiers = base.breakdown.disqualifiers.map((rule) => {
      const override = activeOverride(base.account_id, rule.key);
      return { ...rule, overridden: override !== undefined, override_id: override?.id ?? null };
    });
    const excluded = disqualifiers.filter((rule) => rule.matched && !rule.overridden);
    const standing =
      base.standing === "CUSTOMER"
        ? "CUSTOMER"
        : excluded.length > 0
          ? "DISQUALIFIED"
          : base.fit < minFit
            ? "BELOW_FIT"
            : "RANKED";
    const band: Band | null =
      standing !== "RANKED"
        ? null
        : base.priority >= hotThreshold
          ? "HOT"
          : base.priority >= warmThreshold
            ? "WARM"
            : "COLD";
    return {
      ...base,
      standing,
      band,
      breakdown: { ...base.breakdown, disqualifiers, standing, band },
      overrides: overrideRows.filter(
        (row) => row.account_id === base.account_id && row.service_id === base.service_id,
      ),
    };
  }

  /** Every prospect row with the overrides applied and its rank in the ranking. */
  function currentRows(): ProspectRow[] {
    const rows = prospectRows.map((row) => {
      const base = scoreViews.find((score) => score.account_id === row.account.id);
      if (base === undefined) {
        return row;
      }
      const score = currentScore(base);
      const labels = score.breakdown.disqualifiers
        .filter((rule) => rule.matched && !rule.overridden)
        .map((rule) => rule.label);
      return {
        ...row,
        standing: score.standing,
        band: score.band,
        reason:
          score.standing === "DISQUALIFIED"
            ? { min_fit: null, disqualifier_labels: labels, customer_marked_by_name: null }
            : score.standing === "RANKED"
              ? null
              : row.reason,
      };
    });
    const ranking = rows.filter((row) => row.standing === "RANKED").sort(byRanking);
    return rows.map((row) => {
      const position = ranking.indexOf(row);
      return { ...row, rank: position === -1 ? null : position + 1 };
    });
  }

  return [
    http.get("/api/v1/services/{id}/prospects", ({ query, response }) => {
      const standing = query.get("standing") ?? "RANKED";
      const bands = query.getAll("band");
      const countries = query.getAll("country_code");
      const industries = query.getAll("industry");
      const q = query.get("q") ?? "";
      const sort = query.get("sort") ?? "priority";
      const page = Number(query.get("page") ?? 1);
      const pageSize = Number(query.get("page_size") ?? PAGE_SIZE_DEFAULT);
      if (!Number.isInteger(page) || page < 1) {
        return validation("page", "Must be 1 or more.");
      }
      if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > PAGE_SIZE_MAX) {
        return validation("page_size", `Must be between 1 and ${String(PAGE_SIZE_MAX)}.`);
      }
      const filtered = currentRows().filter(
        (row) =>
          (countries.length === 0 ||
            (row.account.country_code !== null && countries.includes(row.account.country_code))) &&
          (industries.length === 0 ||
            (row.account.industry !== null && industries.includes(row.account.industry))) &&
          (q === "" || matchesQuery(row, q)),
      );
      const ranked = filtered.filter((row) => row.standing === "RANKED");
      const items = filtered
        .filter(
          (row) =>
            row.standing === standing &&
            (bands.length === 0 || (row.band !== null && bands.includes(row.band))),
        )
        .sort(sorts[sort] ?? byRanking);
      return response(200).json({
        items: items.slice((page - 1) * pageSize, page * pageSize),
        page,
        page_size: pageSize,
        total: items.length,
        band_counts: Object.fromEntries(
          BANDS.map((band) => [band, ranked.filter((row) => row.band === band).length]),
        ),
      });
    }),
    http.get("/api/v1/accounts/{id}/scores/{service_id}", ({ params, response }) => {
      const found = scoreViews.find((candidate) => candidate.account_id === params.id);
      if (found === undefined) {
        return errorResponse(notFound, 404);
      }
      const ranking = currentRows();
      const score = currentScore(found);
      const rank = ranking.find((row) => row.account.id === params.id)?.rank ?? null;
      return response(200).json({ ...score, rank });
    }),
    http.get("/api/v1/accounts/{id}/findings", ({ params, query, response }) => {
      const status = query.get("status") ?? "ACTIVE";
      const serviceId = query.get("service_id");
      const questionId = query.get("question_id");
      const size = (points: number | null) => (points === null ? -1 : Math.abs(points));
      return response(200).json(
        findings
          .filter(
            (candidate) =>
              candidate.account_id === params.id &&
              candidate.status === status &&
              (serviceId === null || candidate.service_id === serviceId) &&
              (questionId === null || candidate.question.id === questionId),
          )
          .sort(
            (left, right) =>
              size(right.points) - size(left.points) ||
              right.observed_at.localeCompare(left.observed_at),
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
        const base = scoreViews.find((candidate) => candidate.account_id === params.id);
        if (base === undefined) {
          return errorResponse(notFound, 404);
        }
        const body = await request.json();
        const rule = base.breakdown.disqualifiers.find(
          (candidate) => candidate.key === body.rule_key && candidate.matched,
        );
        if (rule === undefined) {
          return validation("rule_key", "No rule of this key excludes the account.");
        }
        if (activeOverride(params.id, body.rule_key) !== undefined) {
          return errorResponse(
            errorEnvelope("CONFLICT", "An exception is already active for this rule."),
            409,
          );
        }
        const created: Override = {
          id: `ovr-${String(nextId++)}`,
          account_id: params.id,
          service_id: params.service_id,
          rule_key: body.rule_key,
          note: body.note,
          rule_label: rule.label,
          status: "ACTIVE",
          created_by_name: olgaAdmin.display_name,
          created_at: "2026-09-26T09:00:00Z",
          revoked_by_name: null,
          revoked_at: null,
          run_id: `run-rescore-${String(nextId++)}`,
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
      if (current.status !== "ACTIVE") {
        return errorResponse(errorEnvelope("CONFLICT", "The exception was already revoked."), 409);
      }
      const revoked: Override = {
        ...current,
        status: "REVOKED",
        revoked_by_name: olgaAdmin.display_name,
        revoked_at: "2026-09-26T10:00:00Z",
        run_id: `run-rescore-${String(nextId++)}`,
      };
      overrideRows[index] = revoked;
      return response(200).json(revoked);
    }),
  ];
}
