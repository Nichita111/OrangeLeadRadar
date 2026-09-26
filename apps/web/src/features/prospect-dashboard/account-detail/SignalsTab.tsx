/**
 * The Signals tab (`FR-072`, `FR-074`, `FR-131`): the account's signals for the service, filtered
 * by status (the api's) and by question (over the loaded list), each with its evidence.
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useFindings, type FindingStatus, type FindingView } from "../../../api/prospects";
import { Button } from "../../../components/Button";
import { Chip } from "../../../components/Chip";
import { Quote } from "../../../components/score/Quote";
import { QueryErrorState } from "../../../components/States";
import { useRuntimeConfig } from "../../../shell/config-context";
import { confidenceWord, strengthLabel } from "../../../shell/formatting";
import { DECIDED_BY_LABELS, FINDING_STATUS_LABELS } from "../../../shell/labels";
import { EvidencePanel } from "./EvidencePanel";

const STATUSES: FindingStatus[] = ["ACTIVE", "REJECTED", "SUPERSEDED"];
const CONTROL = "rounded-control border border-border bg-surface px-3 text-sm text-text";

function isStatus(value: string): value is FindingStatus {
  return STATUSES.some((status) => status === value);
}

export function SignalsTab({
  accountId,
  serviceId,
  findingId,
}: {
  accountId: string;
  serviceId: string;
  findingId: string | null;
}) {
  const config = useRuntimeConfig();
  const [, setParams] = useSearchParams();
  const [status, setStatus] = useState<FindingStatus>("ACTIVE");
  const [question, setQuestion] = useState("");
  const findings = useFindings(accountId, serviceId, status);

  const loaded = findings.data;
  useEffect(() => {
    if (findingId !== null && loaded !== undefined) {
      document.getElementById(`signal-${findingId}`)?.scrollIntoView();
    }
  }, [findingId, loaded]);

  const questions = [
    ...new Map((loaded ?? []).map((item) => [item.question.key, item.question.text])),
  ];
  const shown = (loaded ?? []).filter((item) => question === "" || item.question.key === question);

  const toggleEvidence = (item: FindingView) => {
    setParams(findingId === item.id ? { tab: "signals" } : { tab: "signals", finding: item.id });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Question
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
            }}
          >
            <option value="">All questions</option>
            {questions.map(([key, text]) => (
              <option key={key} value={key}>
                {text}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Status
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={status}
            onChange={(event) => {
              if (isStatus(event.target.value)) {
                setStatus(event.target.value);
              }
            }}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {FINDING_STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {findings.isError && (
        <QueryErrorState error={findings.error} onRetry={() => void findings.refetch()} />
      )}
      {loaded !== undefined && shown.length === 0 && (
        <p className="text-sm text-text-secondary">No signals for this filter.</p>
      )}
      <ul className="flex flex-col gap-4">
        {shown.map((item) => (
          <li
            key={item.id}
            id={`signal-${item.id}`}
            className="flex flex-col gap-2 rounded-card border border-border bg-surface p-5"
          >
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="font-medium text-text">{item.question.text}</span>
              <Chip>{strengthLabel(item.strength)}</Chip>
              {item.option !== null && (
                <span className="text-text-secondary">{item.option.label}</span>
              )}
              <span
                className="text-text-secondary"
                title={item.confidence.toFixed(2)}
              >{`${confidenceWord(item.confidence, config)} confidence`}</span>
              <span className="text-text-tertiary">{DECIDED_BY_LABELS[item.decided_by]}</span>
            </div>
            <Quote
              quote={item.quote}
              quoteEn={item.quote_en}
              url={item.document.url}
              sourceType={item.document.source_type}
              observedAt={item.observed_at}
            />
            <div>
              <Button
                size="small"
                aria-expanded={findingId === item.id}
                onClick={() => {
                  toggleEvidence(item);
                }}
              >
                Evidence
              </Button>
            </div>
            {findingId === item.id && <EvidencePanel finding={item} />}
          </li>
        ))}
      </ul>
    </div>
  );
}
