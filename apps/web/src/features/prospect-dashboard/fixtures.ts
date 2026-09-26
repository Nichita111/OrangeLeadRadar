/**
 * Typed fixtures of the Prospects and Account detail screens and `fixtureFetch`, the router that
 * answers their contracts (`API-39` to `API-45`, and the catalogues they read). Component tests
 * stub `fetch` with it; the development mock (`api/pending/devMock.ts`) installs it in the
 * browser. The accounts are the [Examples](/architecture/rules.md#examples): Lufthansa Group is
 * Example 1, the excluded account is Example 2.
 */
import type { AuthenticatedUser } from "../../api/auth";
import type { Account } from "../../api/accounts";
import type { Industry, Market } from "../../api/industriesAndMarkets";
import type {
  EvidenceView,
  FindingView,
  Override,
  ProspectRow,
  ScoreBreakdown,
  ScoreView,
} from "../../api/prospects";
import type { ScoringConfig, ScoringConfigSummary } from "../../api/scoring";
import type { Service } from "../../api/services";

export const adminUser: AuthenticatedUser = {
  id: "user-admin",
  email: "admin@leadradar.local",
  display_name: "Olga Admin",
  role: "ADMIN",
};

export const salesUser: AuthenticatedUser = {
  id: "user-sales",
  email: "sales@leadradar.local",
  display_name: "Ana Sales",
  role: "SALES",
};

function service(id: string, name: string, status: Service["status"]): Service {
  return {
    id,
    code: name.toUpperCase().replace(/ /g, "_"),
    name,
    description: "",
    value_proposition: "",
    status,
    question_count: 4,
    active_version: status === "ACTIVE" ? 3 : null,
    draft_version: null,
  };
}

export const services: Service[] = [
  service("svc-1", "Intelligent Automation", "ACTIVE"),
  service("svc-2", "Legacy Migration", "INACTIVE"),
  service("svc-3", "Cloud Cost Control", "ACTIVE"),
];

export const industries: Industry[] = [
  {
    code: "AEROSPACE_AVIATION",
    label: "Aerospace and aviation",
    status: "ACTIVE",
    account_count: 2,
  },
  {
    code: "LOGISTICS_TRANSPORT",
    label: "Logistics and transport",
    status: "ACTIVE",
    account_count: 1,
  },
];

export const markets: Market[] = [
  { code: "DACH", name: "DACH", country_codes: ["DE", "AT", "CH"], status: "ACTIVE" },
];

const activeSummary: ScoringConfigSummary = {
  id: "cfg-3",
  service_id: "svc-1",
  version: 3,
  status: "ACTIVE",
  change_note: null,
  activated_at: "2026-09-01T08:00:00Z",
  activated_by_name: "Olga Admin",
};

export const scoringSummaries: ScoringConfigSummary[] = [activeSummary];

export const scoringConfig: ScoringConfig = {
  ...activeSummary,
  settings: {
    fit_weight: 0.4,
    intent_weight: 0.6,
    min_fit: 40,
    hot_threshold: 75,
    warm_threshold: 40,
    weight_values: { HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0 },
    strength_values: { WEAK: 0.25, MEDIUM: 0.75, STRONG: 1 },
    default_half_life_days: {},
    min_decay: 0.05,
    negative_factor: 1,
    intent_saturation: 0.5,
    unknown_match: 0.5,
    icp_criteria: [],
    questions: [],
    disqualifiers: [],
  },
};

function account(
  id: string,
  name: string,
  domain: string,
  countryCode: string,
  industry: string,
  parent: Account["parent"] = null,
): Account {
  return {
    id,
    name,
    domain,
    country_code: countryCode,
    industry,
    parent,
    aliases: [],
    attribute_origin: {},
    active_run_id: null,
    crunchbase_id: null,
    employee_count: null,
    last_refreshed_at: "2026-09-25T06:00:00Z",
    linkedin_url: null,
    next_refresh_at: null,
    notes: null,
    operational_complexity: "HIGH",
    origin: "IMPORTED",
    revenue_eur: null,
    sources: [],
    status: "ACTIVE",
  };
}

export const accounts: Account[] = [
  account("acc-dhl", "DHL Group", "dhl.com", "DE", "LOGISTICS_TRANSPORT"),
  account("acc-lh", "Lufthansa Group", "lufthansa.com", "DE", "AEROSPACE_AVIATION", {
    id: "acc-holding",
    name: "Lufthansa Holding",
  }),
  account("acc-fr", "Aerofrance", "aerofrance.example", "FR", "AEROSPACE_AVIATION"),
];

function row(
  rank: number | null,
  accountId: string,
  scores: Pick<ProspectRow, "fit" | "intent" | "priority" | "standing" | "band">,
  extra: Partial<ProspectRow> = {},
): ProspectRow {
  const found = accounts.find((candidate) => candidate.id === accountId);
  if (found === undefined) {
    throw new Error(`unknown fixture account ${accountId}`);
  }
  return {
    rank,
    account: {
      id: found.id,
      name: found.name,
      domain: found.domain,
      country_code: found.country_code,
      industry: found.industry,
    },
    ...scores,
    reason: null,
    top_signals: [],
    finding_count: 3,
    unread_alerts: 0,
    as_of: "2026-09-25T06:00:00Z",
    last_refreshed_at: "2026-09-25T06:00:00Z",
    ...extra,
  };
}

export const prospectRows: ProspectRow[] = [
  row(
    1,
    "acc-dhl",
    { fit: 88, intent: 72, priority: 78, standing: "RANKED", band: "HOT" },
    {
      unread_alerts: 2,
      top_signals: [
        {
          question_key: "AI_INITIATIVE",
          question_text: "AI and automation projects",
          strength: "STRONG",
          observed_at: "2026-09-04T00:00:00Z",
        },
        {
          question_key: "COST_PROGRAM",
          question_text: "Cost programme",
          strength: "MEDIUM",
          observed_at: "2026-07-25T00:00:00Z",
        },
      ],
    },
  ),
  row(
    2,
    "acc-lh",
    { fit: 94, intent: 38, priority: 60, standing: "RANKED", band: "WARM" },
    {
      top_signals: [
        {
          question_key: "COST_PROGRAM",
          question_text: "Cost programme",
          strength: "STRONG",
          observed_at: "2026-08-12T00:00:00Z",
        },
      ],
    },
  ),
  row(
    null,
    "acc-fr",
    { fit: 69, intent: 38, priority: 50, standing: "DISQUALIFIED", band: null },
    {
      reason: {
        min_fit: null,
        disqualifier_labels: ["Outside DACH"],
        customer_marked_by_name: null,
      },
    },
  ),
];

function breakdown(region: "MATCH" | "MISMATCH", disqualified: boolean): ScoreBreakdown {
  return {
    settings_version: 3,
    as_of: "2026-09-25T06:00:00Z",
    fit: {
      value: disqualified ? 69 : 94,
      criteria: [
        {
          key: "SECTOR",
          kind: "INDUSTRY",
          weight: "HIGH",
          weight_value: 3,
          attribute: "AEROSPACE_AVIATION",
          match: "MATCH",
          credit: 1,
          points: 37.5,
        },
        {
          key: "REGION",
          kind: "GEOGRAPHY",
          weight: "MEDIUM",
          weight_value: 2,
          attribute: region === "MATCH" ? "DE" : "FR",
          match: region,
          credit: region === "MATCH" ? 1 : 0,
          points: region === "MATCH" ? 25 : 0,
        },
        {
          key: "SIZE",
          kind: "EMPLOYEE_RANGE",
          weight: "LOW",
          weight_value: 1,
          attribute: null,
          match: "UNKNOWN",
          credit: 0.5,
          points: 6.25,
        },
        {
          key: "COMPLEXITY",
          kind: "OPERATIONAL_COMPLEXITY",
          weight: "MEDIUM",
          weight_value: 2,
          attribute: "HIGH",
          match: "MATCH",
          credit: 1,
          points: 25,
        },
      ],
    },
    intent: {
      value: 38,
      positive_sum: 3.181981,
      negative_sum: 1.654074,
      max_positive: 8,
      questions: [
        {
          question_key: "COST_PROGRAM",
          question_text: "Cost programme",
          polarity: "POSITIVE",
          weight: "HIGH",
          weight_value: 3,
          finding_id: "fnd-cost",
          strength: "STRONG",
          decay: 0.707107,
          observed_at: "2026-08-12T00:00:00Z",
          value: 0.707107,
          points: 53.033,
        },
        {
          question_key: "AUTOMATION_HIRING",
          question_text: "Automation hiring",
          polarity: "POSITIVE",
          weight: "MEDIUM",
          weight_value: 2,
          finding_id: "fnd-hire",
          strength: "MEDIUM",
          decay: 0.707107,
          observed_at: "2026-08-27T00:00:00Z",
          value: 0.53033,
          points: 26.517,
        },
        {
          question_key: "AI_INITIATIVE",
          question_text: "AI and automation projects",
          polarity: "POSITIVE",
          weight: "HIGH",
          weight_value: 3,
          finding_id: null,
          strength: null,
          decay: null,
          observed_at: null,
          value: 0,
          points: 0,
        },
        {
          question_key: "IN_HOUSE_AUTOMATION",
          question_text: "In-house automation capability",
          polarity: "NEGATIVE",
          weight: "MEDIUM",
          weight_value: 2,
          finding_id: "fnd-inhouse",
          strength: "STRONG",
          decay: 0.827037,
          observed_at: "2026-06-17T00:00:00Z",
          value: 0.827037,
          points: -41.352,
        },
      ],
    },
    disqualifiers: [
      {
        key: "OUTSIDE_REGION",
        label: "Outside DACH",
        kind: "ICP_MISMATCH",
        criterion_key: "REGION",
        question_key: null,
        matched: disqualified,
        overridden: false,
        override_id: null,
        finding_id: null,
      },
    ],
    priority: disqualified ? 50 : 60,
    standing: disqualified ? "DISQUALIFIED" : "RANKED",
    band: disqualified ? null : "WARM",
  };
}

function scoreView(accountId: string, disqualified: boolean): ScoreView {
  return {
    score_id: `score-${accountId}`,
    account_id: accountId,
    service_id: "svc-1",
    scoring_version: 3,
    as_of: "2026-09-25T06:00:00Z",
    fit: disqualified ? 69 : 94,
    intent: 38,
    priority: disqualified ? 50 : 60,
    standing: disqualified ? "DISQUALIFIED" : "RANKED",
    band: disqualified ? null : "WARM",
    rank: disqualified ? null : 2,
    breakdown: breakdown(disqualified ? "MISMATCH" : "MATCH", disqualified),
    overrides: [],
    lead_feedback: null,
    last_crm_sync: null,
  };
}

/** Example 1: ranked, `WARM`. */
export const rankedScore = scoreView("acc-lh", false);
/** Example 2: `DISQUALIFIED` by `OUTSIDE_REGION`. */
export const excludedScore = scoreView("acc-fr", true);
export const scoreViews: ScoreView[] = [rankedScore, excludedScore];

function finding(
  id: string,
  questionKey: string,
  text: string,
  polarity: FindingView["question"]["polarity"],
  strength: FindingView["strength"],
  quote: string,
  quoteEn: string | null,
  plugin: FindingView["document"]["plugin_code"],
  points: number | null,
  extra: Partial<FindingView> = {},
): FindingView {
  return {
    id,
    account_id: "acc-lh",
    service_id: "svc-1",
    question: { id: `q-${questionKey}`, key: questionKey, text, polarity },
    question_revision: 1,
    confidence: 0.9,
    quote,
    quote_en: quoteEn,
    rationale: "",
    observed_at: "2026-08-12T00:00:00Z",
    strength,
    decided_by: "CLASSIFIER",
    status: "ACTIVE",
    option: null,
    document: {
      id: `doc-${id}`,
      title: null,
      url: `https://${plugin.toLowerCase()}.example/${id}`,
      source_type: "NEWS",
      plugin_code: plugin,
      language: "de",
      published_at: null,
    },
    points,
    feedback: null,
    ...extra,
  };
}

export const findings: FindingView[] = [
  finding(
    "fnd-cost",
    "COST_PROGRAM",
    "Cost programme",
    "POSITIVE",
    "STRONG",
    "Wir senken die Kosten um 500 Millionen Euro.",
    "We are cutting costs by 500 million euros.",
    "GDELT",
    53.033,
  ),
  finding(
    "fnd-cost-old",
    "COST_PROGRAM",
    "Cost programme",
    "POSITIVE",
    "WEAK",
    "Ein weiteres Sparprogramm wurde angekündigt.",
    null,
    "RSS",
    null,
  ),
  finding(
    "fnd-hire",
    "AUTOMATION_HIRING",
    "Automation hiring",
    "POSITIVE",
    "MEDIUM",
    "Wir suchen Automatisierungsingenieure.",
    "We are hiring automation engineers.",
    "CAREERS",
    26.517,
    { decided_by: "LLM" },
  ),
  finding(
    "fnd-inhouse",
    "IN_HOUSE_AUTOMATION",
    "In-house automation capability",
    "NEGATIVE",
    "STRONG",
    "Unser eigenes Automatisierungszentrum bleibt bestehen.",
    "Our own automation centre remains.",
    "WEBSITE",
    -41.352,
  ),
];

const EXCERPTS: Record<string, string> = {
  "fnd-cost":
    "Im Rahmen der Strategie 2030: Wir senken die Kosten um 500 Millionen Euro. Weiter so.",
};

export function evidenceFor(findingId: string): EvidenceView | undefined {
  const found = findings.find((candidate) => candidate.id === findingId);
  if (found === undefined) {
    return undefined;
  }
  const excerpt = EXCERPTS[findingId];
  if (excerpt === undefined) {
    return {
      finding_id: findingId,
      document: found.document,
      section: null,
      purged: true,
      excerpt: null,
      quote_start: null,
      quote_end: null,
    };
  }
  const start = excerpt.indexOf(found.quote);
  return {
    finding_id: findingId,
    document: found.document,
    section: "Strategy 2030",
    purged: false,
    excerpt,
    quote_start: start,
    quote_end: start + found.quote.length,
  };
}

export function requestUrl(input: string | URL | Request): string {
  return typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
}

/** The JSON body of a request, or `null` when it has none. */
export function requestBody(init: RequestInit | undefined): unknown {
  return typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : null;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function errorResponse(status: number, code: string, message: string): Response {
  return jsonResponse({ error: { code, message } }, status);
}

export interface FixtureOverrides {
  /** The signed-in user (`API-03`); the Admin by default. */
  user?: AuthenticatedUser;
  /** Replaces the answer of a route, keyed `"<METHOD> <path>"` (path without the query). */
  routes?: Record<string, (init: RequestInit | undefined) => Response>;
}

/**
 * The fixture router. `API-39` filters only by exact `standing` and `band`; the fixture order is
 * the ranking. `API-44` and `API-45` change the override list and nothing else: they neither
 * rescore nor change a breakdown.
 */
export function fixtureFetch(overrides: FixtureOverrides = {}) {
  const overrideRows: Override[] = [];
  let nextOverrideId = 1;

  return (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = new URL(requestUrl(input), "http://localhost");
    const method = init?.method ?? "GET";
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const custom = overrides.routes?.[`${method} ${path}`];
    if (custom !== undefined) {
      return Promise.resolve(custom(init));
    }
    return Promise.resolve(answer(method, path, url.searchParams, init));
  };

  function answer(
    method: string,
    path: string,
    query: URLSearchParams,
    init: RequestInit | undefined,
  ): Response {
    if (method === "GET") {
      if (path === "/auth/me") {
        return jsonResponse(overrides.user ?? adminUser);
      }
      if (path === "/services") {
        return jsonResponse(services);
      }
      if (path === "/industries") {
        return jsonResponse(industries);
      }
      if (path === "/markets") {
        return jsonResponse(markets);
      }
      if (path === "/services/svc-1/scoring-configs") {
        return jsonResponse(scoringSummaries);
      }
      if (path === `/scoring-configs/${scoringConfig.id}`) {
        return jsonResponse(scoringConfig);
      }
      if (path === "/services/svc-1/prospects") {
        const standing = query.get("standing") ?? "RANKED";
        const band = query.get("band");
        const items = prospectRows.filter(
          (item) => item.standing === standing && (band === null || item.band === band),
        );
        const ranked = prospectRows.filter((item) => item.standing === "RANKED");
        const count = (name: string) => ranked.filter((item) => item.band === name).length;
        return jsonResponse({
          items,
          page: 1,
          page_size: 25,
          total: items.length,
          band_counts: { HOT: count("HOT"), WARM: count("WARM"), COLD: count("COLD") },
        });
      }
      const accountMatch = /^\/accounts\/([^/]+)$/.exec(path);
      if (accountMatch !== null) {
        const found = accounts.find((candidate) => candidate.id === accountMatch[1]);
        return found === undefined ? notFound() : jsonResponse(found);
      }
      const scoreMatch = /^\/accounts\/([^/]+)\/scores\/svc-1$/.exec(path);
      if (scoreMatch !== null) {
        const found = scoreViews.find((candidate) => candidate.account_id === scoreMatch[1]);
        return found === undefined
          ? notFound()
          : jsonResponse({ ...found, overrides: overrideRows });
      }
      if (/^\/accounts\/acc-lh\/findings$/.test(path)) {
        const status = query.get("status") ?? "ACTIVE";
        return jsonResponse(findings.filter((candidate) => candidate.status === status));
      }
      const evidenceMatch = /^\/findings\/([^/]+)\/evidence$/.exec(path);
      if (evidenceMatch !== null) {
        const evidence = evidenceFor(evidenceMatch[1] ?? "");
        return evidence === undefined ? notFound() : jsonResponse(evidence);
      }
    }
    if (method === "POST") {
      if (path === "/auth/logout") {
        return new Response(null, { status: 204 });
      }
      const addMatch = /^\/accounts\/([^/]+)\/scores\/([^/]+)\/overrides$/.exec(path);
      if (addMatch !== null) {
        const body = requestBody(init) as { rule_key: string; note: string };
        if (
          overrideRows.some((row2) => row2.rule_key === body.rule_key && row2.status === "ACTIVE")
        ) {
          return errorResponse(409, "CONFLICT", "An exception is already active for this rule.");
        }
        const created: Override = {
          id: `ovr-${String(nextOverrideId++)}`,
          account_id: addMatch[1] ?? "",
          service_id: addMatch[2] ?? "",
          rule_key: body.rule_key,
          note: body.note,
          rule_label: "Outside DACH",
          status: "ACTIVE",
          created_by_name: adminUser.display_name,
          created_at: "2026-09-26T09:00:00Z",
          revoked_by_name: null,
          revoked_at: null,
          run_id: "run-rescore",
        };
        overrideRows.push(created);
        return jsonResponse(created);
      }
      const revokeMatch = /^\/overrides\/([^/]+)\/revoke$/.exec(path);
      if (revokeMatch !== null) {
        const index = overrideRows.findIndex((candidate) => candidate.id === revokeMatch[1]);
        const current = overrideRows[index];
        if (current === undefined) {
          return notFound();
        }
        const revoked: Override = {
          ...current,
          status: "REVOKED",
          revoked_by_name: adminUser.display_name,
          revoked_at: "2026-09-26T10:00:00Z",
          run_id: "run-rescore",
        };
        overrideRows[index] = revoked;
        return jsonResponse(revoked);
      }
    }
    return notFound();
  }
}

function notFound(): Response {
  return errorResponse(404, "NOT_FOUND", "Not found.");
}
