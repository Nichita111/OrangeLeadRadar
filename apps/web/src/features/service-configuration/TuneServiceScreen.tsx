import { useState } from "react";
import { useParams } from "react-router";

import { ApiError } from "../../api/client";
import type { Schemas } from "../../api/contract";
import {
  useAccountChoices,
  useQuestionPreview,
  useScoringConfigs,
  useScoringPreview,
  useServiceQuestions,
  type QuestionPreviewRequest,
} from "../../api/serviceConfiguration";
import { Button } from "../../components/Button";
import { Callout } from "../../components/Callout";
import { Input, Select } from "../../components/controls";
import { ConfidenceWord } from "../../shell/ConfidenceWord";
import { enumLabel, strengthLabel } from "../../shell/format";
import { PageHeader } from "../../shell/PageHeader";
import { screenWording } from "../../shell/states/degradation";

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";
const ALL_SOURCE_TYPES: Schemas["DocumentSourceType"][] = [
  "NEWS",
  "COMPANY_PUBLICATION",
  "JOB_POSTING",
  "COMPANY_PROFILE",
];
const NEW_QUESTION = "new";

/** The unavailable wording of a `503` or `429` (FR-027 States), else the error's message. */
function ErrorNotice({ error }: { error: Error }) {
  const wording =
    error instanceof ApiError
      ? screenWording(error.envelope.error.code, error.envelope.error.details?.dependency)
      : null;
  return <Callout kind="error">{wording?.headline ?? error.message}</Callout>;
}

/** S-CFG-05, S-CFG-06: Try it and Preview impact for one service, Admin only. */
export function TuneServiceScreen() {
  const { id = "" } = useParams();
  return (
    <>
      <PageHeader
        title="Try it and preview impact"
        lead="Ask a question against a text or an account, and see what the draft scoring would change. Nothing is saved."
      />
      <TryIt serviceId={id} />
      <PreviewImpact serviceId={id} />
    </>
  );
}

function TryIt({ serviceId }: { serviceId: string }) {
  const questions = useServiceQuestions(serviceId);
  const accounts = useAccountChoices();
  const preview = useQuestionPreview();
  const [questionId, setQuestionId] = useState(NEW_QUESTION);
  const [text, setText] = useState("");
  const [answerType, setAnswerType] = useState<"YES_NO" | "SCALE">("YES_NO");
  const [hints, setHints] = useState("");
  const [mode, setMode] = useState<"text" | "account">("text");
  const [sample, setSample] = useState("");
  const [accountId, setAccountId] = useState("");

  const run = () => {
    const question: Partial<QuestionPreviewRequest> =
      questionId === NEW_QUESTION
        ? {
            text,
            answer_type: answerType,
            source_types: ALL_SOURCE_TYPES,
            hint_terms: hints
              .split(",")
              .map((term) => term.trim())
              .filter((term) => term !== ""),
          }
        : { question_id: questionId };
    const target = mode === "text" ? { sample_text: sample } : { account_id: accountId };
    preview.mutate({ service_id: serviceId, ...question, ...target });
  };

  const ready =
    (questionId !== NEW_QUESTION || text.trim() !== "") &&
    (mode === "text" ? sample.trim() !== "" : accountId !== "");

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4">
      <h2 className="m-0 text-section font-semibold">Try it</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className={LABEL}>
          Question
          <Select
            value={questionId}
            onChange={(event) => {
              setQuestionId(event.target.value);
            }}
          >
            <option value={NEW_QUESTION}>New question</option>
            {(questions.data ?? []).map((question) => (
              <option key={question.id} value={question.id}>
                {question.key}: {question.text}
              </option>
            ))}
          </Select>
        </label>
        {questionId === NEW_QUESTION && (
          <>
            <label className={`${LABEL} min-w-80 flex-1`} htmlFor="try-it-text">
              Question text
              <Input
                id="try-it-text"
                value={text}
                placeholder="Does the company announce a cost-reduction programme?"
                onChange={(event) => {
                  setText(event.target.value);
                }}
              />
            </label>
            <label className={LABEL} htmlFor="try-it-answer">
              Answer
              <Select
                id="try-it-answer"
                value={answerType}
                onChange={(event) => {
                  setAnswerType(event.target.value === "SCALE" ? "SCALE" : "YES_NO");
                }}
              >
                <option value="YES_NO">Yes/no</option>
                <option value="SCALE">Scale</option>
              </Select>
            </label>
            <label className={LABEL} htmlFor="try-it-hints">
              Hint terms (comma separated)
              <Input
                id="try-it-hints"
                value={hints}
                onChange={(event) => {
                  setHints(event.target.value);
                }}
              />
            </label>
          </>
        )}
      </div>
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
        <label className={LABEL}>
          Account
          <Select
            value={accountId}
            onChange={(event) => {
              setAccountId(event.target.value);
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
      )}
      <div className="flex items-center gap-3">
        <Button disabled={!ready || preview.isPending} onClick={run}>
          {preview.isPending ? "Running…" : "Try it"}
        </Button>
        <span className="text-hint text-text-tertiary">Nothing is saved.</span>
      </div>
      {preview.error !== null && <ErrorNotice error={preview.error} />}
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

function scoreLabel(score: Schemas["ScoringPreviewScore"]): string {
  const band = score.band === null ? enumLabel(score.standing) : enumLabel(score.band);
  const rank = score.rank === null ? "" : ` · #${String(score.rank)}`;
  return `${String(score.priority)} · ${band}${rank}`;
}

function PreviewImpact({ serviceId }: { serviceId: string }) {
  const configs = useScoringConfigs(serviceId);
  const preview = useScoringPreview();
  const draft = (configs.data ?? []).find((config) => config.status === "DRAFT");

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4">
      <h2 className="m-0 text-section font-semibold">Preview impact</h2>
      <div className="flex items-center gap-3">
        <Button
          disabled={draft === undefined || preview.isPending}
          onClick={() => {
            if (draft !== undefined) {
              preview.mutate(draft.id);
            }
          }}
        >
          {preview.isPending ? "Computing…" : "Preview impact"}
        </Button>
        <span className="text-hint text-text-tertiary">
          {draft === undefined
            ? "This service has no draft scoring version."
            : `Draft v${String(draft.version)}, nothing is written.`}
        </span>
      </div>
      {preview.error !== null && <ErrorNotice error={preview.error} />}
      {preview.data !== undefined && (
        <>
          <p className="m-0 text-text-secondary">
            {`v${String(preview.data.active_version)} active, draft v${String(preview.data.draft_version)}: ${String(preview.data.changes.length)} accounts change, ${String(preview.data.unchanged_count)} unchanged.`}
          </p>
          {preview.data.changes.length > 0 && (
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  <th scope="col" className="px-4 py-2 font-medium">
                    Account
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Current
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Proposed
                  </th>
                </tr>
              </thead>
              <tbody>
                {preview.data.changes.map((change) => (
                  <tr key={change.account.id} className="border-b border-border last:border-b-0">
                    <td className="px-4 py-2">{change.account.name}</td>
                    <td className="px-4 py-2">{scoreLabel(change.current)}</td>
                    <td className="px-4 py-2">{scoreLabel(change.proposed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
