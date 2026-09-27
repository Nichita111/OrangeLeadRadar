import { useState } from "react";

import { useImportAccounts } from "../../../api/accounts";
import type { Schemas } from "../../../api/contract";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip, type ChipTone } from "../../../components/Chip";
import { PageHeader } from "../../../shell/PageHeader";

type ImportResult = Schemas["ImportResult"];
type Outcome = Schemas["ImportRowOutcome"];

/** The header row of `AccountImportRow`, offered as a template (`FR-042`). */
const TEMPLATE_HEADER =
  "domain,name,country_code,industry,employee_count,revenue_eur,aliases,newsroom_url," +
  "careers_url,investor_relations_url,rss_url,operational_complexity,linkedin_url,notes\n";

const OUTCOME: Record<Outcome, { label: string; tone: ChipTone; sentence: string }> = {
  CREATED: { label: "New", tone: "positive", sentence: "A new account is created." },
  UPDATED: { label: "Updated", tone: "cool", sentence: "The existing account is updated." },
  POSSIBLE_DUPLICATE: {
    label: "Possible duplicate",
    tone: "caution",
    sentence: "Looks like an existing account under another domain; it is imported as new.",
  },
  INVALID: { label: "Invalid", tone: "negative", sentence: "This row is skipped." },
};

function Counts({ result }: { result: ImportResult }) {
  const rows: [string, number, string][] = [
    ["New", result.created, "accounts that will be created"],
    ["Updated", result.updated, "existing accounts whose empty fields are filled"],
    ["Possible duplicates", result.duplicates, "may be an account you already have"],
    ["Invalid", result.invalid, "rows that are skipped"],
  ];
  return (
    <dl className="m-0 grid grid-cols-4 gap-3">
      {rows.map(([label, count, meaning]) => (
        <div key={label} className="rounded-card border border-border bg-surface p-3">
          <dt className="text-hint text-text-tertiary">{label}</dt>
          <dd className="num m-0 text-section font-semibold">{count}</dd>
          <dd className="m-0 text-hint text-text-tertiary">{meaning}</dd>
        </div>
      ))}
    </dl>
  );
}

/** S-ACC-02: Account import, `/accounts/import`. FR-041 to FR-043, FR-139, FR-140. */
export function AccountImportScreen() {
  const [file, setFile] = useState<File | null>(null);
  const check = useImportAccounts();
  const run = useImportAccounts();
  const step = run.data !== undefined ? 3 : check.data !== undefined ? 2 : 1;
  const attention = (check.data?.rows ?? []).filter((row) => row.outcome !== "CREATED");
  const templateUrl = `data:text/csv;charset=utf-8,${encodeURIComponent(TEMPLATE_HEADER)}`;

  return (
    <>
      <PageHeader
        title="Account import"
        lead="Add or update many accounts from a CSV file. Nothing is written until you press Import."
        action={
          <a href={templateUrl} download="accounts-template.csv" className="underline">
            Download the template
          </a>
        }
      />
      <ol className="m-0 mb-4 flex list-none gap-6 p-0 text-hint">
        {["Choose file", "Review the check", "Import"].map((label, index) => (
          <li
            key={label}
            className={index + 1 === step ? "font-semibold text-text" : "text-text-tertiary"}
          >
            {index + 1}. {label}
          </li>
        ))}
      </ol>
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-hint text-text-tertiary">
          CSV file
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const chosen = event.target.files?.[0] ?? null;
              setFile(chosen);
              run.reset();
              if (chosen !== null) {
                check.mutate({ file: chosen, dryRun: true });
              }
            }}
          />
        </label>
        {check.isPending && <p className="m-0 text-text-secondary">Checking the file…</p>}
        {check.error !== null && <Callout kind="error">{check.error.message}</Callout>}
        {check.data !== undefined && run.data === undefined && (
          <>
            <Counts result={check.data} />
            {attention.length > 0 && (
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {attention.map((row) => (
                  <li key={row.line} className="flex flex-col gap-1">
                    <span>
                      Line {row.line} · {row.domain ?? "no domain"}{" "}
                      <Chip tone={OUTCOME[row.outcome].tone}>{OUTCOME[row.outcome].label}</Chip>
                    </span>
                    <span className="text-hint text-text-secondary">
                      {OUTCOME[row.outcome].sentence}
                      {row.errors.map((error) => ` ${error.field}: ${error.message}.`).join("")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div>
              <Button
                variant="primary"
                disabled={
                  file === null ||
                  run.isPending ||
                  check.data.created + check.data.updated + check.data.duplicates === 0
                }
                onClick={() => {
                  if (file !== null) {
                    run.mutate({ file, dryRun: false });
                  }
                }}
              >
                {run.isPending ? "Importing…" : "Import"}
              </Button>
            </div>
          </>
        )}
        {run.error !== null && <Callout kind="error">{run.error.message}</Callout>}
        {run.data !== undefined && (
          <>
            <Counts result={run.data} />
            <Callout kind="accent">
              {`${String(run.data.created + run.data.updated + run.data.duplicates)} accounts imported. Each new one gets its first refresh from Refresh now on Accounts or from the scheduler.`}
            </Callout>
            <div>
              <ButtonLink to="/accounts">Open Accounts</ButtonLink>
            </div>
          </>
        )}
      </div>
    </>
  );
}
