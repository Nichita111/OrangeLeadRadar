// The development mock's in-memory accounts, runs, contacts, outreach drafts and alerts, shared by
// every handler module so an account imported, accepted from Discovery or refreshed is the same row
// everywhere (TypeScript Mock layer).
// Temporary: a run advances on the clock, one stage every `STAGE_MS`, with counters made up per
// stage; nothing is fetched, classified or rescored. The store is kept in `sessionStorage`, so a
// reload keeps what was imported and refreshed, and a new tab starts from the fixtures.
import type { Schemas } from "../api/contract";
import { contacts } from "./accountsAndDiscovery.fixtures";
import { alerts } from "./alerts.fixtures";
import { accounts } from "./prospectsAndEvidence.fixtures";

type Account = Schemas["Account"];
type AlertView = Schemas["AlertView"];
type Contact = Schemas["Contact"];
type OutreachDraft = Schemas["OutreachDraft"];
type Run = Schemas["Run"];
type Stage = Schemas["PipelineRunStage"];

const STORAGE_KEY = "leadradar-mock-store";

/** How long the mock keeps a run in each stage, so its progress can be watched. */
const STAGE_MS = 1500;

/** The stages each kind passes through, as the worker's Run lifecycle orders them. */
const STAGES: Record<Run["kind"], Stage[]> = {
  ACCOUNT_REFRESH: ["FETCH", "PROCESS", "TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RECLASSIFY: ["TRIAGE", "CLASSIFY", "EVIDENCE", "SCORE"],
  RESCORE: ["SCORE"],
  DISCOVERY: ["FETCH", "TRIAGE", "SCORE"],
  EVALUATION: ["CLASSIFY"],
};

/** The counters a stage adds once it is done. */
const STAGE_COUNTERS: Partial<Record<Stage, Record<string, number>>> = {
  FETCH: { documents_fetched: 24 },
  PROCESS: { documents_new: 9, documents_kept: 7, passages: 31 },
  CLASSIFY: { pairs_classified: 42, pairs_escalated: 3 },
  EVIDENCE: { findings_created: 4 },
};

const DISCOVERY_COUNTERS: Partial<Record<Stage, Record<string, number>>> = {
  FETCH: { news_searched: 18 },
  TRIAGE: { organisations_found: 7 },
  SCORE: { candidates: 1 },
};

export interface MockStore {
  accounts: Account[];
  runs: Run[];
  contacts: Contact[];
  drafts: OutreachDraft[];
  alerts: AlertView[];
  newId(): string;
  startRun(
    kind: Run["kind"],
    refs: Pick<Run, "account" | "service" | "trigger" | "requested_by_name">,
    onFinish?: () => void,
  ): Run;
  /** The run as the clock leaves it now; a run that has just finished applies its effect. */
  settle(run: Run): Run;
  cancel(run: Run): void;
  /** Keeps the store for the next page load of this tab. */
  save(): void;
}

interface Saved {
  accounts: Account[];
  runs: Run[];
  contacts: Contact[];
  drafts: OutreachDraft[];
  alerts: AlertView[];
  startedAt: [string, number][];
  nextId: number;
}

function load(): Saved | undefined {
  try {
    const text = sessionStorage.getItem(STORAGE_KEY);
    return text === null ? undefined : (JSON.parse(text) as Saved);
  } catch {
    return undefined;
  }
}

export function createMockStore(): MockStore {
  const saved = load();
  const accountRows =
    saved?.accounts ?? accounts.map((row) => ({ ...row, sources: [...row.sources] }));
  const runs: Run[] = saved?.runs ?? [];
  const contactRows: Contact[] = saved?.contacts ?? contacts.map((row) => ({ ...row }));
  const drafts: OutreachDraft[] = saved?.drafts ?? [];
  const alertRows: AlertView[] = saved?.alerts ?? alerts.map((row) => ({ ...row }));
  const startedAt = new Map<string, number>(saved?.startedAt ?? []);
  // A run's effect on finishing is not kept across a reload; its account's state is.
  const finishers = new Map<string, () => void>();
  let nextId = saved?.nextId ?? 1;

  function newId(): string {
    return `00000000-0000-4000-8000-${String(nextId++).padStart(12, "0")}`;
  }

  function finish(run: Run, status: Run["status"], at: number): void {
    run.status = status;
    run.stage = null;
    run.finished_at = new Date(at).toISOString();
    const account = accountRows.find((row) => row.active_run_id === run.id);
    if (account !== undefined) {
      account.active_run_id = null;
      if (status === "SUCCEEDED") {
        account.last_refreshed_at = run.finished_at;
      }
    }
    if (status === "SUCCEEDED") {
      finishers.get(run.id)?.();
    }
    finishers.delete(run.id);
  }

  function settle(run: Run): Run {
    const created = startedAt.get(run.id);
    if (created === undefined || (run.status !== "QUEUED" && run.status !== "RUNNING")) {
      return run;
    }
    const stages = STAGES[run.kind];
    const now = Date.now();
    const step = Math.floor((now - created) / STAGE_MS);
    if (step === 0) {
      return run;
    }
    run.started_at ??= new Date(created + STAGE_MS).toISOString();
    const counters = run.kind === "DISCOVERY" ? DISCOVERY_COUNTERS : STAGE_COUNTERS;
    const done = stages.slice(0, Math.min(step - 1, stages.length));
    run.progress = Object.assign({}, ...done.map((stage) => counters[stage] ?? {})) as Record<
      string,
      number
    >;
    run.ai_cost_eur = done.includes("CLASSIFY") ? 0.04 : 0;
    if (step > stages.length) {
      finish(run, "SUCCEEDED", created + (stages.length + 1) * STAGE_MS);
      return run;
    }
    run.status = "RUNNING";
    run.stage = stages[step - 1] ?? null;
    return run;
  }

  function startRun(
    kind: Run["kind"],
    refs: Pick<Run, "account" | "service" | "trigger" | "requested_by_name">,
    onFinish?: () => void,
  ): Run {
    const now = Date.now();
    const run: Run = {
      id: newId(),
      kind,
      status: "QUEUED",
      stage: null,
      progress: {},
      errors: [],
      question: null,
      created_at: new Date(now).toISOString(),
      started_at: null,
      finished_at: null,
      ai_cost_eur: 0,
      ...refs,
    };
    runs.unshift(run);
    startedAt.set(run.id, now);
    if (onFinish !== undefined) {
      finishers.set(run.id, onFinish);
    }
    return run;
  }

  function cancel(run: Run): void {
    finish(run, "CANCELLED", Date.now());
  }

  function save(): void {
    const value: Saved = {
      accounts: accountRows,
      runs,
      contacts: contactRows,
      drafts,
      alerts: alertRows,
      startedAt: [...startedAt],
      nextId,
    };
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      // Storage blocked: the store then lasts until the page reloads.
    }
  }

  return {
    accounts: accountRows,
    runs,
    contacts: contactRows,
    drafts,
    alerts: alertRows,
    newId,
    startRun,
    settle,
    cancel,
    save,
  };
}
