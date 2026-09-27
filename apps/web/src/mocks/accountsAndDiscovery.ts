// The development mock of the contacts (`API-25` to `API-28`) and Discovery (`API-29` to
// `API-32`) contracts (TypeScript Mock layer). Temporary: the persona is suggested from a few
// job-title words instead of the classifier, a domain is normalised by stripping the scheme, `www.`
// and the path, the candidate list ignores `service_id`, and a run advances one status per read.
// The accounts and runs the mock creates are answered here too, so a new account opens and its
// refresh finishes; every other account and run goes on to the api.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse } from "../api/authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../api/contract";
import { contacts, discoveredLater, discoveryCandidates } from "./accountsAndDiscovery.fixtures";
import { accounts, services } from "./prospectsAndEvidence.fixtures";

type Account = Schemas["Account"];
type Contact = Schemas["Contact"];
type Persona = Schemas["ContactPersona"];
type Run = Schemas["Run"];

const CONTACT_FIELDS = ["full_name", "job_title", "source_url", "persona"];
const RETAIN_UNTIL = "2027-09-27";
const NOW = "2026-09-27T09:00:00Z";

const personaWords: [RegExp, Persona][] = [
  [/\b(cio|chief information officer)\b/i, "CIO"],
  [/\b(cto|chief technology officer)\b/i, "CTO"],
  [/\b(coo|chief operating officer)\b/i, "COO"],
  [/\b(cfo|chief financial officer)\b/i, "CFO"],
  [/\b(ciso|chief information security officer)\b/i, "CISO"],
  [/transformation|digitali/i, "HEAD_OF_DIGITAL_TRANSFORMATION"],
  [/automation|automatisierung/i, "HEAD_OF_AUTOMATION"],
  [/process excellence|prozessexzellenz/i, "HEAD_OF_PROCESS_EXCELLENCE"],
  [/shared service|business services/i, "HEAD_OF_SHARED_SERVICES"],
];

function suggestPersona(jobTitle: string): Persona {
  return personaWords.find(([words]) => words.test(jobTitle))?.[1] ?? "OTHER";
}

function normaliseDomain(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^[a-z]+:\/\//, "")
    .replace(/^www\./, "")
    .replace(/[/?#].*$/, "")
    .replace(/\.$/, "");
}

function validation(fields: { field: string; message: string }[]): Response {
  return errorResponse(errorEnvelope("VALIDATION", "The input is invalid.", { fields }), 422);
}

/** `422` for a body field outside the shape or a blank required one, else null. */
function contactErrors(body: Record<string, unknown>, required: boolean): Response | null {
  const unknown = Object.keys(body).filter((field) => !CONTACT_FIELDS.includes(field));
  if (unknown.length > 0) {
    return validation(unknown.map((field) => ({ field, message: "Not a contact field." })));
  }
  const blank = ["full_name", "job_title", "source_url"].filter((field) => {
    const value = body[field];
    return (required || value !== undefined) && (typeof value !== "string" || value.trim() === "");
  });
  return blank.length === 0
    ? null
    : validation(blank.map((field) => ({ field, message: "Required." })));
}

export function createAccountsAndDiscoveryHandlers() {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const contactRows = contacts.map((row) => ({ ...row }));
  const candidateRows = discoveryCandidates.map((row) => ({ ...row }));
  const createdAccounts: Account[] = [];
  const runs: Run[] = [];
  let nextId = 1;
  const notFound = errorEnvelope("NOT_FOUND", "Not found.");

  function newId(prefix: string): string {
    return `${prefix}-${String(nextId++)}`;
  }

  function newRun(kind: Run["kind"], refs: Pick<Run, "account" | "service">): Run {
    const run: Run = {
      id: `00000000-0000-4000-8000-${String(nextId++).padStart(12, "0")}`,
      kind,
      trigger: "USER",
      status: "QUEUED",
      stage: null,
      progress: {},
      errors: [],
      account: refs.account,
      service: refs.service,
      question: null,
      requested_by_name: "Olga Admin",
      created_at: NOW,
      started_at: null,
      finished_at: null,
      ai_cost_eur: 0,
    };
    runs.push(run);
    return run;
  }

  /** Moves a run one status on; a finished run applies its effect. */
  function advance(run: Run): void {
    if (run.status === "QUEUED") {
      run.status = "RUNNING";
      run.started_at = NOW;
      run.stage = run.kind === "DISCOVERY" ? "TRIAGE" : "FETCH";
      return;
    }
    if (run.status !== "RUNNING") {
      return;
    }
    run.status = "SUCCEEDED";
    run.stage = null;
    run.finished_at = NOW;
    if (run.kind === "DISCOVERY" && run.service !== null) {
      const serviceId = run.service.id;
      if (!candidateRows.some((row) => row.id === discoveredLater.id)) {
        candidateRows.push({ ...discoveredLater, service_id: serviceId });
      }
    }
    const refreshed = createdAccounts.find((row) => row.active_run_id === run.id);
    if (refreshed !== undefined) {
      refreshed.active_run_id = null;
      refreshed.last_refreshed_at = NOW;
    }
  }

  function accountWithDomain(domain: string): { id: string } | undefined {
    return [...accounts, ...createdAccounts].find((row) => row.domain === domain);
  }

  return [
    http.get("/api/v1/accounts/{id}/contacts", ({ params, response }) =>
      response(200).json(contactRows.filter((row) => row.account_id === params.id)),
    ),
    http.post("/api/v1/accounts/{id}/contacts", async ({ params, request, response }) => {
      const body = await request.json();
      const invalid = contactErrors(body, true);
      if (invalid !== null) {
        return invalid;
      }
      const created: Contact = {
        id: newId("con"),
        account_id: params.id,
        full_name: body.full_name,
        job_title: body.job_title,
        source_url: body.source_url,
        persona: body.persona ?? suggestPersona(body.job_title),
        persona_origin: body.persona === undefined ? "CLASSIFIER" : "MANUAL",
        retain_until: RETAIN_UNTIL,
      };
      contactRows.push(created);
      return response(200).json(created);
    }),
    http.patch("/api/v1/contacts/{id}", async ({ params, request, response }) => {
      const current = contactRows.find((row) => row.id === params.id);
      if (current === undefined) {
        return errorResponse(notFound, 404);
      }
      const body = await request.json();
      const invalid = contactErrors(body, false);
      if (invalid !== null) {
        return invalid;
      }
      Object.assign(current, body);
      if (body.persona !== undefined) {
        current.persona_origin = "MANUAL";
      } else if (body.job_title !== undefined && current.persona_origin === "CLASSIFIER") {
        current.persona = suggestPersona(body.job_title);
      }
      return response(200).json(current);
    }),
    http.delete("/api/v1/contacts/{id}", ({ params, response }) => {
      const index = contactRows.findIndex((row) => row.id === params.id);
      if (index === -1) {
        return errorResponse(notFound, 404);
      }
      contactRows.splice(index, 1);
      return response(204).empty();
    }),
    http.post("/api/v1/services/{id}/discovery-runs", ({ params, response }) => {
      const running = runs.find(
        (run) =>
          run.kind === "DISCOVERY" &&
          run.service?.id === params.id &&
          (run.status === "QUEUED" || run.status === "RUNNING"),
      );
      const name = services.find((row) => row.id === params.id)?.name ?? "";
      return response(202).json(
        running ?? newRun("DISCOVERY", { account: null, service: { id: params.id, name } }),
      );
    }),
    http.get("/api/v1/discovery-candidates", ({ request, response }) => {
      const status = new URL(request.url).searchParams.get("status");
      const items = candidateRows
        .filter((row) => status === null || row.status === status)
        .sort((left, right) => right.fit_estimate - left.fit_estimate);
      return response(200).json({ items, page: 1, page_size: 25, total: items.length });
    }),
    http.post("/api/v1/discovery-candidates/{id}/accept", async ({ params, request, response }) => {
      const current = candidateRows.find((row) => row.id === params.id);
      if (current === undefined) {
        return errorResponse(notFound, 404);
      }
      if (current.status !== "PENDING") {
        return errorResponse(errorEnvelope("CONFLICT", "This suggestion is already decided."), 409);
      }
      const body = await request.json();
      const given = current.domain ?? body.domain;
      if (given === undefined || normaliseDomain(given) === "") {
        return validation([{ field: "domain", message: "A domain is required." }]);
      }
      const domain = normaliseDomain(given);
      const existing = accountWithDomain(domain);
      if (existing !== undefined) {
        return errorResponse(
          errorEnvelope("CONFLICT", "An account with this domain exists.", {
            entity_id: existing.id,
          }),
          409,
        );
      }
      const id = newId("acc");
      const refresh = newRun("ACCOUNT_REFRESH", {
        account: { id, name: current.name },
        service: null,
      });
      const created: Account = {
        id,
        name: current.name,
        domain,
        country_code: current.country_code ?? "",
        industry: current.industry,
        status: "ACTIVE",
        relationship_status: "PROSPECT",
        origin: "DISCOVERED",
        last_refreshed_at: null,
        active_run_id: refresh.id,
        employee_count: current.employee_count,
        revenue_eur: null,
        operational_complexity: null,
        attribute_origin: {},
        parent: null,
        crunchbase_id: null,
        linkedin_url: null,
        notes: null,
        aliases: [current.name],
        sources: [
          { url: `https://${domain}/`, kind: "WEBSITE", origin: "MANUAL", status: "ACTIVE" },
        ],
        next_refresh_at: null,
      };
      createdAccounts.push(created);
      Object.assign(current, { status: "ACCEPTED", domain, account_id: id });
      return response(200).json(created);
    }),
    http.post("/api/v1/discovery-candidates/{id}/reject", async ({ params, request, response }) => {
      const current = candidateRows.find((row) => row.id === params.id);
      if (current === undefined) {
        return errorResponse(notFound, 404);
      }
      if (current.status !== "PENDING") {
        return errorResponse(errorEnvelope("CONFLICT", "This suggestion is already decided."), 409);
      }
      const body = await request.json();
      Object.assign(current, { status: "REJECTED", reject_reason: body.reason ?? null });
      return response(200).json(current);
    }),
    // Only what the mock created; anything else falls through to the api.
    http.get("/api/v1/accounts/{id}", ({ params, response }) => {
      const found = createdAccounts.find((row) => row.id === params.id);
      return found === undefined ? undefined : response(200).json(found);
    }),
    http.get("/api/v1/runs/{id}", ({ params, response }) => {
      const found = runs.find((run) => run.id === params.id);
      if (found === undefined) {
        return undefined;
      }
      advance(found);
      return response(200).json(found);
    }),
  ];
}
