// The development mock of Accounts (`API-20` to `API-24`), refresh and Runs (`API-33` to
// `API-36`), the first half of SC-A: import the demo accounts, refresh one and watch its run
// (TypeScript Mock layer). Temporary: an industry code is not checked against the active
// industries, an import that updates an account enqueues no RESCORE, an attribute change is not
// rescored, and a refresh leaves the account's score as its fixture has it.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse } from "../api/authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../api/contract";
import { mockSessionUser } from "./authentication";
import type { MockStore } from "./store";

type Account = Schemas["Account"];
type AccountRow = Schemas["AccountRow"];
type ImportRowResult = Schemas["ImportRowResult"];
type Run = Schemas["Run"];

/** `PAGE_SIZE_DEFAULT`, `PAGE_SIZE_MAX` and `IMPORT_MAX_ROWS` of the api's runtime. */
const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_MAX = 200;
const IMPORT_MAX_ROWS = 2000;

/** The source columns of an import row and the kind each one adds. */
const SOURCE_COLUMNS: [string, Schemas["AccountSourceKind"]][] = [
  ["newsroom_url", "NEWSROOM"],
  ["careers_url", "CAREERS"],
  ["investor_relations_url", "INVESTOR_RELATIONS"],
  ["rss_url", "RSS_FEED"],
];

const ADMIN_CANCEL: Run["kind"][] = ["RECLASSIFY", "RESCORE", "EVALUATION"];

/** Account identity, loosely: lower case, no scheme, `www.`, path or trailing dot. */
function normaliseDomain(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^[a-z]+:\/\//, "")
    .replace(/^www\./, "")
    .replace(/[/?#].*$/, "")
    .replace(/\.$/, "");
}

/** The rows of a CSV file with a header row; a quoted field may hold commas and doubled quotes. */
function parseCsv(text: string): Record<string, string>[] {
  const records: string[][] = [];
  let field = "";
  let record: string[] = [];
  let quoted = false;
  for (let index = 0; index < text.length; index++) {
    const char = text.charAt(index);
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index++;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      record.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") {
        index++;
      }
      record.push(field);
      records.push(record);
      record = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field !== "" || record.length > 0) {
    record.push(field);
    records.push(record);
  }
  const [header, ...rows] = records.filter((row) => row.some((value) => value.trim() !== ""));
  if (header === undefined) {
    return [];
  }
  return rows.map((row) =>
    Object.fromEntries(header.map((column, index) => [column.trim(), (row[index] ?? "").trim()])),
  );
}

function toRow(account: Account): AccountRow {
  const { id, name, domain, country_code, industry, status, origin } = account;
  const { last_refreshed_at, active_run_id, relationship_status } = account;
  return {
    id,
    name,
    domain,
    country_code,
    industry,
    status,
    origin,
    relationship_status,
    last_refreshed_at,
    active_run_id,
  };
}

function validation(fields: { field: string; message: string }[]): Response {
  return errorResponse(errorEnvelope("VALIDATION", "The input is invalid.", { fields }), 422);
}

function pageOf(
  pageParam: string | null,
  pageSizeParam: string | null,
): { page: number; pageSize: number } | Response {
  const page = Number(pageParam ?? 1);
  const pageSize = Number(pageSizeParam ?? PAGE_SIZE_DEFAULT);
  if (!Number.isInteger(page) || page < 1) {
    return validation([{ field: "page", message: "Must be 1 or more." }]);
  }
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > PAGE_SIZE_MAX) {
    return validation([
      { field: "page_size", message: `Must be between 1 and ${String(PAGE_SIZE_MAX)}.` },
    ]);
  }
  return { page, pageSize };
}

export function createAccountsAndRunsHandlers(store: MockStore) {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const notFound = () => errorResponse(errorEnvelope("NOT_FOUND", "Not found."), 404);

  function byDomain(domain: string): Account | undefined {
    return store.accounts.find((row) => row.domain === domain);
  }

  function newAccount(
    fields: Pick<Account, "name" | "domain" | "origin"> & Partial<Account>,
  ): Account {
    const account: Account = {
      id: store.newId(),
      country_code: null,
      industry: null,
      status: "ACTIVE",
      relationship_status: "PROSPECT",
      last_refreshed_at: null,
      active_run_id: null,
      employee_count: null,
      revenue_eur: null,
      operational_complexity: null,
      attribute_origin: {},
      parent: null,
      crunchbase_id: null,
      linkedin_url: null,
      notes: null,
      aliases: [fields.name],
      sources: [
        {
          url: `https://${fields.domain}/`,
          kind: "WEBSITE",
          origin: "MANUAL",
          status: "ACTIVE",
        },
      ],
      next_refresh_at: null,
      ...fields,
    };
    store.accounts.push(account);
    return account;
  }

  /** One import row checked against the store; a row that passes is applied unless `dryRun`. */
  function importRow(
    row: Record<string, string>,
    line: number,
    dryRun: boolean,
    seen: Set<string>,
  ): ImportRowResult {
    const domain = normaliseDomain(row["domain"] ?? "");
    const name = row["name"] ?? "";
    const errors: { field: string; message: string }[] = [];
    if (domain === "") {
      errors.push({ field: "domain", message: "Required." });
    }
    if (name === "") {
      errors.push({ field: "name", message: "Required." });
    }
    const country = row["country_code"] ?? "";
    if (country !== "" && !/^[A-Z]{2}$/.test(country)) {
      errors.push({ field: "country_code", message: "Two capital letters, as ISO 3166-1." });
    }
    for (const field of ["employee_count", "revenue_eur"]) {
      const value = row[field] ?? "";
      if (value !== "" && !/^\d+$/.test(value)) {
        errors.push({ field, message: "A whole number." });
      }
    }
    const complexity = row["operational_complexity"] ?? "";
    if (complexity !== "" && !["LOW", "MEDIUM", "HIGH"].includes(complexity)) {
      errors.push({ field: "operational_complexity", message: "LOW, MEDIUM or HIGH." });
    }
    if (errors.length > 0) {
      return { line, domain: domain || null, outcome: "INVALID", account_id: null, errors };
    }
    const filled: Partial<Account> = {
      ...(country === "" ? {} : { country_code: country }),
      ...(row["industry"] ? { industry: row["industry"] } : {}),
      ...(row["employee_count"] ? { employee_count: Number(row["employee_count"]) } : {}),
      ...(row["revenue_eur"] ? { revenue_eur: Number(row["revenue_eur"]) } : {}),
      ...(complexity === ""
        ? {}
        : { operational_complexity: complexity as Account["operational_complexity"] }),
      ...(row["linkedin_url"] ? { linkedin_url: row["linkedin_url"] } : {}),
      ...(row["notes"] ? { notes: row["notes"] } : {}),
    };
    const sources = SOURCE_COLUMNS.filter(([column]) => (row[column] ?? "") !== "").map(
      ([column, kind]) => ({
        url: row[column] ?? "",
        kind,
        origin: "MANUAL" as const,
        status: "ACTIVE" as const,
      }),
    );
    const aliases = (row["aliases"] ?? "")
      .split(";")
      .map((alias) => alias.trim())
      .filter((alias) => alias !== "");
    const existing = byDomain(domain);
    if (existing !== undefined) {
      if (!dryRun) {
        Object.assign(existing, filled);
        for (const key of Object.keys(filled)) {
          existing.attribute_origin[key] = "MANUAL";
        }
        existing.sources = [
          ...existing.sources,
          ...sources.filter((source) => !existing.sources.some((row) => row.url === source.url)),
        ];
      }
      return { line, domain, outcome: "UPDATED", account_id: existing.id, errors: [] };
    }
    const sameName = store.accounts.some(
      (account) => account.name.toLowerCase() === name.toLowerCase(),
    );
    if (sameName || seen.has(domain)) {
      return { line, domain, outcome: "POSSIBLE_DUPLICATE", account_id: null, errors: [] };
    }
    seen.add(domain);
    if (dryRun) {
      return { line, domain, outcome: "CREATED", account_id: null, errors: [] };
    }
    const created = newAccount({ name, domain, origin: "IMPORTED", ...filled });
    created.aliases = [name, ...aliases];
    created.sources = [...created.sources, ...sources];
    created.attribute_origin = Object.fromEntries(
      Object.keys(filled).map((key) => [key, "MANUAL"]),
    );
    return { line, domain, outcome: "CREATED", account_id: created.id, errors: [] };
  }

  return [
    http.get("/api/v1/accounts", ({ query, response }) => {
      const paging = pageOf(query.get("page"), query.get("page_size"));
      if (paging instanceof Response) {
        return paging;
      }
      const q = (query.get("q") ?? "").trim().toLowerCase();
      const status = query.get("status");
      const country = query.get("country_code");
      const industry = query.get("industry");
      const origin = query.get("origin");
      const items = store.accounts
        .filter(
          (account) =>
            (q === "" ||
              [account.name, account.domain, ...account.aliases].some((value) =>
                value.toLowerCase().includes(q),
              )) &&
            (status === null || account.status === status) &&
            (country === null || account.country_code === country) &&
            (industry === null || account.industry === industry) &&
            (origin === null || account.origin === origin),
        )
        .sort((left, right) => left.name.localeCompare(right.name))
        .map(toRow);
      const { page, pageSize } = paging;
      return response(200).json({
        items: items.slice((page - 1) * pageSize, page * pageSize),
        page,
        page_size: pageSize,
        total: items.length,
      });
    }),
    http.post("/api/v1/accounts", async ({ request, response }) => {
      const body = await request.json();
      const domain = normaliseDomain(body.domain);
      const errors = [
        ...(domain === "" ? [{ field: "domain", message: "Required." }] : []),
        ...(body.name.trim() === "" ? [{ field: "name", message: "Required." }] : []),
      ];
      if (errors.length > 0) {
        return validation(errors);
      }
      const existing = byDomain(domain);
      if (existing !== undefined) {
        return errorResponse(
          errorEnvelope("CONFLICT", "An account with this domain exists.", {
            entity_id: existing.id,
          }),
          409,
        );
      }
      const { sources, aliases, parent_account_id, ...fields } = body;
      const parent = store.accounts.find((row) => row.id === parent_account_id);
      const created = newAccount({
        ...fields,
        name: body.name.trim(),
        domain,
        origin: "MANUAL",
        parent: parent === undefined ? null : { id: parent.id, name: parent.name },
      });
      created.aliases = [created.name, ...aliases];
      created.sources = [
        ...created.sources,
        ...sources.map((source) => ({
          ...source,
          origin: "MANUAL" as const,
          status: "ACTIVE" as const,
        })),
      ];
      return response(200).json(created);
    }),
    http.post("/api/v1/accounts/import", async ({ request, response }) => {
      const form = await request.formData();
      const file = form.get("file");
      const dryRun = form.get("dry_run") !== "false";
      if (!(file instanceof File)) {
        return validation([{ field: "file", message: "A CSV file is required." }]);
      }
      const rows = parseCsv(await file.text());
      if (rows.length > IMPORT_MAX_ROWS) {
        return validation([
          { field: "file", message: `At most ${String(IMPORT_MAX_ROWS)} rows per import.` },
        ]);
      }
      const seen = new Set<string>();
      // Line 1 is the header row.
      const results = rows.map((row, index) => importRow(row, index + 2, dryRun, seen));
      const count = (outcome: ImportRowResult["outcome"]) =>
        results.filter((row) => row.outcome === outcome).length;
      return response(200).json({
        dry_run: dryRun,
        rows: results,
        created: count("CREATED"),
        updated: count("UPDATED"),
        duplicates: count("POSSIBLE_DUPLICATE"),
        invalid: count("INVALID"),
      });
    }),
    http.get("/api/v1/accounts/{id}", ({ params, response }) => {
      const found = store.accounts.find((row) => row.id === params.id);
      if (found === undefined) {
        return notFound();
      }
      if (found.active_run_id !== null) {
        const run = store.runs.find((row) => row.id === found.active_run_id);
        if (run !== undefined) {
          store.settle(run);
        }
      }
      return response(200).json(found);
    }),
    http.patch("/api/v1/accounts/{id}", async ({ params, request, response }) => {
      const found = store.accounts.find((row) => row.id === params.id);
      if (found === undefined) {
        return notFound();
      }
      const { sources, aliases, parent_account_id, ...fields } = await request.json();
      Object.assign(found, fields);
      for (const key of Object.keys(fields)) {
        if (key !== "status" && key !== "notes") {
          found.attribute_origin[key] = "MANUAL";
        }
      }
      if (aliases !== undefined) {
        found.aliases = [found.name, ...aliases.filter((alias) => alias !== found.name)];
      }
      if (sources !== undefined) {
        found.sources = [
          ...found.sources.filter((source) => source.origin === "DETECTED"),
          ...sources.map((source) => ({
            url: source.url,
            kind: source.kind,
            origin: "MANUAL" as const,
            status: source.status,
          })),
        ];
      }
      if (parent_account_id !== undefined) {
        const parent = store.accounts.find((row) => row.id === parent_account_id);
        found.parent = parent === undefined ? null : { id: parent.id, name: parent.name };
      }
      return response(200).json(found);
    }),
    http.post("/api/v1/accounts/{id}/refresh", ({ params, response }) => {
      const found = store.accounts.find((row) => row.id === params.id);
      if (found === undefined) {
        return notFound();
      }
      if (found.status !== "ACTIVE") {
        return errorResponse(errorEnvelope("CONFLICT", "The account is inactive."), 409);
      }
      const active = store.runs.find((row) => row.id === found.active_run_id);
      if (active !== undefined && ["QUEUED", "RUNNING"].includes(store.settle(active).status)) {
        return response(200).json(active);
      }
      const run = store.startRun("ACCOUNT_REFRESH", {
        account: { id: found.id, name: found.name },
        service: null,
        trigger: "USER",
        requested_by_name: mockSessionUser().display_name,
      });
      found.active_run_id = run.id;
      return response(202).json(run);
    }),
    http.get("/api/v1/runs", ({ query, response }) => {
      const paging = pageOf(query.get("page"), query.get("page_size"));
      if (paging instanceof Response) {
        return paging;
      }
      const kind = query.get("kind");
      const status = query.get("status");
      const accountId = query.get("account_id");
      const serviceId = query.get("service_id");
      const items = store.runs
        .map((run) => store.settle(run))
        .filter(
          (run) =>
            (kind === null || run.kind === kind) &&
            (status === null || run.status === status) &&
            (accountId === null || run.account?.id === accountId) &&
            (serviceId === null || run.service?.id === serviceId),
        );
      const { page, pageSize } = paging;
      return response(200).json({
        items: items.slice((page - 1) * pageSize, page * pageSize),
        page,
        page_size: pageSize,
        total: items.length,
      });
    }),
    http.get("/api/v1/runs/{id}", ({ params, response }) => {
      const found = store.runs.find((run) => run.id === params.id);
      return found === undefined ? notFound() : response(200).json(store.settle(found));
    }),
    http.post("/api/v1/runs/{id}/cancel", ({ params, response }) => {
      const found = store.runs.find((run) => run.id === params.id);
      if (found === undefined) {
        return notFound();
      }
      if (ADMIN_CANCEL.includes(found.kind) && mockSessionUser().role !== "ADMIN") {
        return errorResponse(errorEnvelope("FORBIDDEN", "Only an Admin may cancel this run."), 403);
      }
      const current = store.settle(found);
      if (current.status !== "QUEUED" && current.status !== "RUNNING") {
        return errorResponse(errorEnvelope("CONFLICT", "The run has already finished."), 409);
      }
      store.cancel(current);
      return response(200).json(current);
    }),
  ];
}
