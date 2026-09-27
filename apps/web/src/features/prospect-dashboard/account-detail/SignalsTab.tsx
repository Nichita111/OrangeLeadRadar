import { useState } from "react";

import { useFindings, type FindingStatus } from "../../../api/prospectsAndEvidence";
import { Chip } from "../../../components/Chip";
import { Select } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { ConfidenceWord } from "../../../shell/ConfidenceWord";
import { strengthLabel, enumLabel } from "../../../shell/format";
import { DataView } from "../../../shell/states/DataView";
import { FindingQuote } from "../FindingQuote";

const STATUSES: { value: FindingStatus; label: string }[] = [
  { value: "ACTIVE", label: "Counting" },
  { value: "REJECTED", label: "Marked wrong" },
  { value: "SUPERSEDED", label: "Outdated question" },
];

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";

function isStatus(value: string): value is FindingStatus {
  return STATUSES.some((status) => status.value === value);
}

/**
 * The Signals tab (FR-072, FR-074): the account's signals for the service, filtered by status
 * (the api's) and by question (over the loaded list), each with its quote, why it counts and Open
 * original; the stored passage is not shown.
 */
export function SignalsTab({ accountId, serviceId }: { accountId: string; serviceId: string }) {
  const [status, setStatus] = useState<FindingStatus>("ACTIVE");
  const [question, setQuestion] = useState("");
  const findings = useFindings(accountId, serviceId, status);

  const questions = [
    ...new Map((findings.data ?? []).map((item) => [item.question.key, item.question.text])),
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className={LABEL}>
          Question
          <Select
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
          </Select>
        </label>
        <label className={LABEL}>
          Status
          <Select
            value={status}
            onChange={(event) => {
              if (isStatus(event.target.value)) {
                setStatus(event.target.value);
              }
            }}
          >
            {STATUSES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
      </div>

      <DataView
        query={findings}
        isEmpty={(items) => items.length === 0}
        skeleton={<Skeleton className="h-32 w-full" />}
        empty={{ message: "No signals for this filter.", action: null }}
      >
        {(items) => {
          const shown = items.filter((item) => question === "" || item.question.key === question);
          if (shown.length === 0) {
            return <p className="m-0 text-text-secondary">No signals for this filter.</p>;
          }
          return (
            <ul className="m-0 flex list-none flex-col gap-4 p-0">
              {shown.map((item) => (
                <li
                  key={item.id}
                  id={`signal-${item.id}`}
                  className="flex flex-col gap-2 rounded-card border border-border bg-surface p-5"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-medium">{item.question.text}</span>
                    <Chip>{strengthLabel(item.strength)}</Chip>
                    {item.option !== null && (
                      <span className="text-text-secondary">{item.option.label}</span>
                    )}
                    <span className="text-text-secondary">
                      <ConfidenceWord value={item.confidence} /> confidence
                    </span>
                    <span className="text-text-tertiary">{enumLabel(item.decided_by)}</span>
                  </div>
                  <FindingQuote finding={item} />
                  {item.rationale.trim() !== "" && (
                    <p className="m-0 text-text-secondary">
                      <span className="font-medium text-text">Why it counts:</span> {item.rationale}
                    </p>
                  )}
                  {item.document.plugin_code === "GDELT" && (
                    <p className="m-0 text-hint text-text-tertiary">
                      Found by the{" "}
                      <a
                        href="https://www.gdeltproject.org/"
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        GDELT Project
                      </a>
                    </p>
                  )}
                </li>
              ))}
            </ul>
          );
        }}
      </DataView>
    </div>
  );
}
