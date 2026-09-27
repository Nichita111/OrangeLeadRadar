import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import {
  useAcceptCandidate,
  useDiscoveryCandidates,
  useLatestDiscoveryRun,
  useStartDiscovery,
  type CandidateStatus,
  type DiscoveryCandidate,
} from "../../../api/discovery";
import { useIndustries } from "../../../api/industriesAndMarkets";
import { isRunFinal, useRun, type Run } from "../../../api/runs";
import type { Schemas } from "../../../api/contract";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { Select } from "../../../components/controls";
import { ScoreNumber } from "../../../components/score/ScoreNumber";
import { Skeleton } from "../../../components/Skeleton";
import { RelativeTime } from "../../../shell/RelativeTime";
import { countryName, enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";
import { AcceptCandidateDialog } from "./AcceptCandidateDialog";
import { RejectCandidateDialog } from "./RejectCandidateDialog";

const STATUSES: CandidateStatus[] = ["PENDING", "ACCEPTED", "REJECTED"];
const SKELETON_ROWS = [0, 1, 2, 3, 4];

function isStatus(value: string | null): value is CandidateStatus {
  return STATUSES.some((status) => status === value);
}

function runningLabel(run: Run | undefined): string {
  if (run === undefined || run.stage === null) {
    return "Finding…";
  }
  const counters = run.progress;
  const sources = counters["news_searched"] ?? 0;
  const articles = counters["documents_fetched"] ?? 0;
  const companies = counters["organisations_found"] ?? 0;
  return (
    `Finding… ${String(sources)} news source${sources === 1 ? "" : "s"} searched · ` +
    `${String(articles)} articles · ${String(companies)} companies`
  );
}

/** S-DSC-01, S-DSC-02: Suggested accounts, `/suggested-accounts`, any signed-in user. FL-06, WF-09. */
export function SuggestedAccountsScreen() {
  return (
    <>
      <PageHeader
        title="Suggested accounts"
        lead="Companies Discovery found in the news that might need this service. Accept the ones worth pursuing."
      />
      <WithService>{(service) => <SuggestedAccountsList service={service} />}</WithService>
    </>
  );
}

function SuggestedAccountsList({ service }: { service: Schemas["Service"] }) {
  const [params, setParams] = useSearchParams();
  const statusParam = params.get("status");
  const status = isStatus(statusParam) ? statusParam : "PENDING";
  const pageNumber = Number(params.get("page"));
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber : 1;

  const candidates = useDiscoveryCandidates(service.id, status, page);
  const startDiscovery = useStartDiscovery(service.id);
  const latestRun = useLatestDiscoveryRun(service.id);
  const [requestedRunId, setRequestedRunId] = useState<string | null>(null);

  const runningOnLoad = latestRun.data?.items[0];
  const activeRunId =
    requestedRunId ??
    (runningOnLoad !== undefined && !isRunFinal(runningOnLoad) ? runningOnLoad.id : null);
  const activeRun = useRun(activeRunId ?? undefined);
  const isRunning = activeRun.data !== undefined && !isRunFinal(activeRun.data);
  const refetchedForRunRef = useRef<string | null>(null);

  useEffect(() => {
    const data = activeRun.data;
    if (data !== undefined && isRunFinal(data) && refetchedForRunRef.current !== data.id) {
      refetchedForRunRef.current = data.id;
      void candidates.refetch();
    }
  }, [activeRun.data, candidates]);

  async function handleFindNewAccounts() {
    const run = await startDiscovery.mutateAsync();
    setRequestedRunId(run.id);
  }

  // G9: the latest finished run's own candidates decide the note, not the current status filter.
  const latestFinishedRun =
    runningOnLoad !== undefined && isRunFinal(runningOnLoad) ? runningOnLoad : undefined;
  const latestRunCandidates = useDiscoveryCandidates(service.id, undefined, 1);
  const foundNoCrunchbaseMatch =
    latestFinishedRun !== undefined &&
    (latestRunCandidates.data?.items ?? []).every((item) => item.origin !== "CRUNCHBASE_SEARCH");

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="flex flex-col gap-1 text-hint text-text-tertiary">
          Status
          <Select
            value={status}
            onChange={(event) => {
              const next = new URLSearchParams(params);
              if (event.target.value === "PENDING") {
                next.delete("status");
              } else {
                next.set("status", event.target.value);
              }
              next.delete("page");
              setParams(next);
            }}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
        <Button variant="primary" disabled={isRunning} onClick={() => void handleFindNewAccounts()}>
          {isRunning ? "Finding…" : "Find new accounts"}
        </Button>
      </div>

      {isRunning && <Callout kind="accent">{runningLabel(activeRun.data)}</Callout>}
      {activeRun.data?.status === "FAILED" && (
        <Callout kind="error" lead="Discovery failed.">
          {activeRun.data.errors.map((error) => error.message).join(" ")}
        </Callout>
      )}
      {foundNoCrunchbaseMatch && (
        <p className="m-0 text-hint text-text-tertiary">
          These suggestions come from news only; no Crunchbase organisation search is available yet.
        </p>
      )}

      <DataView
        query={candidates}
        isEmpty={(result) => result.items.length === 0}
        skeleton={
          <div className="flex flex-col gap-2" aria-busy="true">
            {SKELETON_ROWS.map((row) => (
              <Skeleton key={row} className="h-14 w-full" />
            ))}
          </div>
        }
        empty={{
          message:
            status === "PENDING"
              ? "No pending candidates. Find new accounts to search the news for companies that might need this service."
              : "No candidates match this status.",
          action: null,
        }}
      >
        {(result) => (
          <CandidatesTable
            items={result.items.filter(
              (item) => status !== "PENDING" || item.status !== "REJECTED",
            )}
            serviceId={service.id}
          />
        )}
      </DataView>
    </>
  );
}

function CandidatesTable({ items, serviceId }: { items: DiscoveryCandidate[]; serviceId: string }) {
  const industries = useIndustries();
  const industryLabels = new Map((industries.data ?? []).map((item) => [item.code, item.label]));
  const [rejecting, setRejecting] = useState<DiscoveryCandidate | null>(null);
  const [accepting, setAccepting] = useState<DiscoveryCandidate | null>(null);
  const accept = useAcceptCandidate(serviceId);

  return (
    <div className="overflow-hidden rounded-card border border-border bg-surface">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">Suggested accounts</caption>
        <thead>
          <tr className="border-b border-border text-hint text-text-tertiary">
            {[
              "Company",
              "Country",
              "Industry",
              "Employees",
              "Fit",
              "Why suggested",
              "Decision",
            ].map((column) => (
              <th key={column} scope="col" className="px-4 py-3 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-border last:border-b-0 align-top">
              <td className="px-4 py-3 font-medium">{item.name}</td>
              <td className="px-4 py-3">
                {item.country_code === null ? "—" : countryName(item.country_code)}
              </td>
              <td className="px-4 py-3">
                {item.industry === null
                  ? "—"
                  : (industryLabels.get(item.industry) ?? item.industry)}
              </td>
              <td className="num px-4 py-3">{item.employee_count ?? "—"}</td>
              <td className="px-4 py-3">
                <ScoreNumber label="Fit" value={item.fit_estimate} />
              </td>
              <td className="max-w-sm px-4 py-3">
                {item.evidence === null ? (
                  <Chip tone="cool">Crunchbase match</Chip>
                ) : (
                  <figure className="m-0 flex flex-col gap-1 border-l-2 border-border pl-3">
                    <blockquote className="m-0">{item.evidence.quote}</blockquote>
                    <figcaption className="text-hint text-text-tertiary">
                      <a
                        href={item.evidence.url}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        {item.evidence.title ?? item.evidence.url}
                      </a>
                      {item.evidence.published_at !== null && (
                        <>
                          {" · "}
                          <RelativeTime at={item.evidence.published_at} />
                        </>
                      )}
                    </figcaption>
                  </figure>
                )}
              </td>
              <td className="px-4 py-3">
                <DecisionCell
                  item={item}
                  onAccept={() => {
                    if (item.domain === null) {
                      setAccepting(item);
                    } else {
                      void accept.mutateAsync({ id: item.id });
                    }
                  }}
                  onReject={() => {
                    setRejecting(item);
                  }}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {accepting !== null && (
        <AcceptCandidateDialog
          candidate={accepting}
          serviceId={serviceId}
          open
          onOpenChange={(open) => {
            if (!open) setAccepting(null);
          }}
        />
      )}
      {rejecting !== null && (
        <RejectCandidateDialog
          candidate={rejecting}
          serviceId={serviceId}
          open
          onOpenChange={(open) => {
            if (!open) setRejecting(null);
          }}
        />
      )}
    </div>
  );
}

function DecisionCell({
  item,
  onAccept,
  onReject,
}: {
  item: DiscoveryCandidate;
  onAccept: () => void;
  onReject: () => void;
}) {
  if (item.status === "ACCEPTED") {
    return (
      <div className="flex flex-col gap-1">
        <Chip tone="positive">Accepted · Refresh queued</Chip>
        {item.account_id !== null && (
          <ButtonLink size="small" to={`/accounts/${item.account_id}`}>
            Open account
          </ButtonLink>
        )}
      </div>
    );
  }
  if (item.status === "REJECTED") {
    return <Chip tone="neutral">Rejected</Chip>;
  }
  return (
    <div className="flex flex-col gap-2">
      {item.domain === null && (
        <p className="m-0 text-hint text-text-tertiary">Accepting will ask for its domain.</p>
      )}
      <div className="flex gap-2">
        <Button size="small" variant="primary" onClick={onAccept}>
          Accept
        </Button>
        <Button size="small" variant="secondary" onClick={onReject}>
          Reject
        </Button>
      </div>
    </div>
  );
}
