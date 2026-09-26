/**
 * [Account import](/features/accounts-and-discovery.md#account-import). Route
 * `/accounts/import`, any signed-in user. WF-07.
 */
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useImportAccounts, type ImportResult, type ImportRowOutcome } from "../../../api/accounts";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip, type ChipTone } from "../../../components/Chip";
import { ErrorState } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { Stepper, type StepState } from "../../../components/motion/Stepper";

/** `FR-042`, the header row of [`AccountImportRow`](/architecture/interfaces.md#accountimportrow). */
const TEMPLATE_HEADER =
  "domain,name,country_code,industry,employee_count,revenue_eur,aliases,newsroom_url,careers_url,investor_relations_url,rss_url,operational_complexity,linkedin_url,notes\n";

const OUTCOME_TONE: Record<ImportRowOutcome, ChipTone> = {
  CREATED: "positive",
  UPDATED: "cool",
  POSSIBLE_DUPLICATE: "caution",
  INVALID: "negative",
};

const OUTCOME_SENTENCE: Record<ImportRowOutcome, string> = {
  CREATED: "A new account will be created.",
  UPDATED: "The existing account will be updated.",
  POSSIBLE_DUPLICATE:
    "This looks like an existing account; it will still be created unless you fix it first.",
  INVALID: "This row will be skipped.",
};

function downloadTemplate() {
  const blob = new Blob([TEMPLATE_HEADER], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "account-import-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function AccountImportScreen() {
  const navigate = useNavigate();
  const importAccounts = useImportAccounts();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dryRunResult, setDryRunResult] = useState<ImportResult | null>(null);
  const [importedResult, setImportedResult] = useState<ImportResult | null>(null);

  const step: "choose" | "review" | "import" =
    importedResult !== null ? "import" : dryRunResult !== null ? "review" : "choose";

  const steps: { key: string; label: string; state: StepState }[] = [
    { key: "choose", label: "Choose file", state: step === "choose" ? "current" : "done" },
    {
      key: "review",
      label: "Review the check",
      state: step === "choose" ? "pending" : step === "review" ? "current" : "done",
    },
    { key: "import", label: "Import", state: step === "import" ? "current" : "pending" },
  ];

  const handleChooseFile = (selected: File) => {
    setFile(selected);
    setImportedResult(null);
    importAccounts.mutate({ file: selected, dryRun: true }, { onSuccess: setDryRunResult });
  };

  const handleImport = () => {
    if (file === null) {
      return;
    }
    importAccounts.mutate({ file, dryRun: false }, { onSuccess: setImportedResult });
  };

  const attentionRows = (dryRunResult?.rows ?? []).filter(
    (row) => row.outcome !== "CREATED" && row.outcome !== "UPDATED",
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-text">Import accounts</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Choose a CSV file, review what it will do, then import the valid rows.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={downloadTemplate}>
            Template: download header row
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              fileInputRef.current?.click();
            }}
          >
            Choose CSV file
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(event) => {
              const selected = event.target.files?.[0];
              if (selected !== undefined) {
                handleChooseFile(selected);
              }
            }}
          />
        </div>
      </div>

      <Stepper steps={steps} />

      {importAccounts.isError && (
        <ErrorState
          message={
            importAccounts.error instanceof ApiError
              ? importAccounts.error.message
              : "Something went wrong."
          }
          onRetry={() => {
            if (file !== null) {
              handleChooseFile(file);
            }
          }}
        />
      )}

      {importedResult !== null && (
        <Callout kind="accent">
          <strong>{importedResult.created + importedResult.updated} accounts were imported.</strong>{" "}
          Each new one gets its first refresh from Refresh now on its Account detail, or from the
          scheduler.
        </Callout>
      )}

      {importedResult === null && dryRunResult !== null && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-text-secondary">
            {dryRunResult.rows.length} rows · {dryRunResult.created} new · {dryRunResult.updated}{" "}
            updated · {dryRunResult.duplicates} possible duplicate · {dryRunResult.invalid} invalid
          </p>

          {attentionRows.length > 0 && (
            <Table caption="Rows that need attention">
              <TableHead>
                <TableRow>
                  <TableHeaderCell>Line</TableHeaderCell>
                  <TableHeaderCell>Domain</TableHeaderCell>
                  <TableHeaderCell>Outcome</TableHeaderCell>
                  <TableHeaderCell>Details</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {attentionRows.map((row) => {
                  const outcome = row.outcome as ImportRowOutcome;
                  return (
                    <TableRow key={row.line}>
                      <TableCell>{row.line}</TableCell>
                      <TableCell>{row.domain ?? "—"}</TableCell>
                      <TableCell>
                        <Chip tone={OUTCOME_TONE[outcome]}>
                          {outcome.replace(/_/g, " ").toLowerCase()}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        {row.errors.length > 0
                          ? row.errors.map((rowError) => rowError.message).join("; ")
                          : OUTCOME_SENTENCE[outcome]}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setFile(null);
                setDryRunResult(null);
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" onClick={handleImport} disabled={importAccounts.isPending}>
              Import {dryRunResult.created + dryRunResult.updated} accounts
            </Button>
          </div>
        </div>
      )}

      {importedResult !== null && (
        <div>
          <Button
            variant="secondary"
            onClick={() => {
              void navigate(`/accounts?origin=IMPORTED`);
            }}
          >
            View imported accounts
          </Button>
        </div>
      )}
    </div>
  );
}
