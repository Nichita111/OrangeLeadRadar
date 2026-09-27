import { useState } from "react";

import type { Schemas } from "../../../api/contract";
import {
  useAccountChoices,
  useQuestionPreview,
  type QuestionPreviewRequest,
} from "../../../api/serviceConfiguration";
import { Button } from "../../../components/Button";
import { Select } from "../../../components/controls";
import { ConfidenceWord } from "../../../shell/ConfidenceWord";
import { strengthLabel } from "../../../shell/format";
import { PreviewErrorNotice } from "../PreviewErrorNotice";

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";

/** The question form's current, possibly unsaved, values that Try it asks. */
export interface TryItQuestion {
  /** The saved question the form edits; absent in Add mode. */
  questionId?: string;
  text: string;
  answer_type: Schemas["SignalQuestionAnswerType"];
  options: Schemas["QuestionOption"][] | null;
  source_types: Schemas["DocumentSourceType"][];
  hint_terms: string[];
}

/** FR-027: runs the form's current question against pasted text or a chosen account. */
export function TryIt({ serviceId, question }: { serviceId: string; question: TryItQuestion }) {
  const preview = useQuestionPreview();
  const [mode, setMode] = useState<"text" | "account">("text");
  const [sample, setSample] = useState("");
  const [accountId, setAccountId] = useState("");

  const run = () => {
    const body: QuestionPreviewRequest = {
      service_id: serviceId,
      ...(question.questionId !== undefined && { question_id: question.questionId }),
      text: question.text,
      answer_type: question.answer_type,
      ...(question.options !== null && { options: question.options }),
      source_types: question.source_types,
      hint_terms: question.hint_terms,
      ...(mode === "text" ? { sample_text: sample } : { account_id: accountId }),
    };
    preview.mutate(body);
  };

  const ready =
    question.text.trim() !== "" && (mode === "text" ? sample.trim() !== "" : accountId !== "");

  return (
    <section
      aria-labelledby="try-it-heading"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
    >
      <h3 id="try-it-heading" className="m-0 text-section font-semibold">
        Try it
      </h3>
      <div role="group" aria-label="Ask against" className="flex gap-1">
        <Button
          size="small"
          variant={mode === "text" ? "primary" : "secondary"}
          aria-pressed={mode === "text"}
          onClick={() => {
            setMode("text");
          }}
        >
          Paste text
        </Button>
        <Button
          size="small"
          variant={mode === "account" ? "primary" : "secondary"}
          aria-pressed={mode === "account"}
          onClick={() => {
            setMode("account");
          }}
        >
          Account
        </Button>
      </div>
      {mode === "text" ? (
        <label className={LABEL}>
          Text
          <textarea
            className="min-h-32 w-full rounded-control border border-control-border bg-surface p-3 text-text"
            value={sample}
            onChange={(event) => {
              setSample(event.target.value);
            }}
          />
        </label>
      ) : (
        <AccountChoice value={accountId} onChange={setAccountId} />
      )}
      <div className="flex items-center gap-3">
        <Button disabled={!ready || preview.isPending} onClick={run}>
          {preview.isPending ? "Running…" : "Try it"}
        </Button>
        <span className="text-hint text-text-tertiary">Nothing is saved.</span>
      </div>
      {preview.error !== null && <PreviewErrorNotice error={preview.error} />}
      {preview.data !== undefined &&
        (preview.data.results.length === 0 ? (
          <p className="m-0 text-text-secondary">No passage to check.</p>
        ) : (
          <ol className="m-0 flex list-decimal flex-col gap-3 pl-5">
            {preview.data.results.map((result, index) => (
              <li key={index} className="flex flex-col gap-1">
                <span>
                  {result.strength === "NONE" ? "No signal" : strengthLabel(result.strength)}
                  {" · "}
                  <ConfidenceWord value={result.p_positive} /> confidence
                  {" · Detailed check: "}
                  {result.escalated ? "yes" : "no"}
                </span>
                {result.quote !== null && (
                  <blockquote className="m-0 border-l-2 border-border pl-3">
                    &ldquo;{result.quote}&rdquo;
                  </blockquote>
                )}
                {result.quote_en !== null && (
                  <p className="m-0 text-text-secondary">EN: &ldquo;{result.quote_en}&rdquo;</p>
                )}
                {result.rationale !== null && (
                  <p className="m-0 text-text-secondary">{result.rationale}</p>
                )}
                {result.document !== null && (
                  <a
                    className="text-hint text-accent underline"
                    href={result.document.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {result.document.title}
                  </a>
                )}
              </li>
            ))}
          </ol>
        ))}
    </section>
  );
}

/** The account to ask against; mounted only in Account mode, so the list loads on demand. */
function AccountChoice({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const accounts = useAccountChoices();
  return (
    <label className={LABEL}>
      Account
      <Select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        <option value="">Choose an account</option>
        {(accounts.data?.items ?? []).map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </Select>
    </label>
  );
}
