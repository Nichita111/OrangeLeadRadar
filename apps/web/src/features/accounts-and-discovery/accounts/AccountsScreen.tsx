/**
 * [Accounts](/features/accounts-and-discovery.md#accounts). Route `/accounts`, any signed-in
 * user. WF-06.
 */
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAccounts, type AccountOrigin, type AccountStatus } from "../../../api/accounts";
import { useIndustries } from "../../../api/industries";
import { Button } from "../../../components/Button";
import { Chip } from "../../../components/Chip";
import { Input } from "../../../components/Input";
import { Select } from "../../../components/Select";
import { EmptyState, ErrorState, SkeletonRows, UnavailableState } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { ShimmerLabel } from "../../../components/motion/ShimmerLabel";
import {
  formatCountryName,
  formatRelativeDate,
  listCountryCodes,
  titleCaseEnum,
} from "../../../shell/formatting";
import { AccountFormDialog } from "./AccountFormDialog";

const COLUMN_COUNT = 6;
const COUNTRY_OPTIONS = listCountryCodes();

export function AccountsScreen() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [formOpen, setFormOpen] = useState(false);
  const { data: industries } = useIndustries();

  const q = searchParams.get("q") ?? "";
  const status = searchParams.get("status") as AccountStatus | null;
  const country = searchParams.get("country_code");
  const industry = searchParams.get("industry");
  const origin = searchParams.get("origin") as AccountOrigin | null;

  const {
    data: page,
    isLoading,
    isError,
    error,
    refetch,
  } = useAccounts({
    q: q.length > 0 ? q : undefined,
    status: status ?? undefined,
    country_code: country ?? undefined,
    industry: industry ?? undefined,
    origin: origin ?? undefined,
  });

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "") {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-text">Accounts</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Bring in the companies you are watching, search or filter the list, and open one for its
            profile.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void navigate("/accounts/import");
            }}
          >
            Import CSV
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              setFormOpen(true);
            }}
          >
            New account
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Input
          id="accounts-search"
          label="Search"
          placeholder="Name, alias or domain"
          value={q}
          onChange={(event) => {
            setFilter("q", event.target.value);
          }}
        />
        <Select
          id="accounts-country"
          label="Country"
          value={country ?? ""}
          onValueChange={(value) => {
            setFilter("country_code", value);
          }}
          options={[
            { value: "", label: "All countries" },
            ...COUNTRY_OPTIONS.map((code) => ({ value: code, label: formatCountryName(code) })),
          ]}
        />
        <Select
          id="accounts-industry"
          label="Industry"
          value={industry ?? ""}
          onValueChange={(value) => {
            setFilter("industry", value);
          }}
          options={[
            { value: "", label: "All industries" },
            ...(industries ?? []).map((entry) => ({ value: entry.code, label: entry.label })),
          ]}
        />
        <Select
          id="accounts-status"
          label="Status"
          value={status ?? ""}
          onValueChange={(value) => {
            setFilter("status", value);
          }}
          options={[
            { value: "", label: "All statuses" },
            { value: "ACTIVE", label: "Active" },
            { value: "INACTIVE", label: "Inactive" },
          ]}
        />
        <Select
          id="accounts-origin"
          label="Origin"
          value={origin ?? ""}
          onValueChange={(value) => {
            setFilter("origin", value);
          }}
          options={[
            { value: "", label: "All origins" },
            { value: "IMPORTED", label: "Imported" },
            { value: "MANUAL", label: "Manual" },
            { value: "DISCOVERED", label: "Discovered" },
          ]}
        />
      </div>

      <Table caption="Accounts">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Domain</TableHeaderCell>
            <TableHeaderCell>Country</TableHeaderCell>
            <TableHeaderCell>Industry</TableHeaderCell>
            <TableHeaderCell>Origin</TableHeaderCell>
            <TableHeaderCell>Refreshed</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && <SkeletonRows rows={4} columns={COLUMN_COUNT} />}
          {!isLoading && isError && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                {error instanceof ApiError && (error.status === 503 || error.status === 429) ? (
                  <UnavailableState
                    dependency={
                      typeof error.details?.dependency === "string"
                        ? error.details.dependency
                        : "The database"
                    }
                    stillWorks={[]}
                  />
                ) : (
                  <ErrorState
                    message={error instanceof ApiError ? error.message : "Something went wrong."}
                    onRetry={() => void refetch()}
                  />
                )}
              </TableCell>
            </TableRow>
          )}
          {!isLoading && !isError && page !== undefined && page.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <EmptyState
                  message="No accounts yet. Import a CSV or add the first one by hand."
                  actionLabel="New account"
                  onAction={() => {
                    setFormOpen(true);
                  }}
                />
              </TableCell>
            </TableRow>
          )}
          {!isLoading &&
            !isError &&
            page?.items.map((account) => (
              <TableRow key={account.id}>
                <TableCell>
                  <button
                    type="button"
                    className="flex items-center gap-2 text-left text-accent hover:underline"
                    onClick={() => {
                      void navigate(`/accounts/${account.id}/profile`);
                    }}
                  >
                    {account.name}
                    {account.status === "INACTIVE" && <Chip tone="neutral">Inactive</Chip>}
                    {account.active_run_id !== null && (
                      <Chip tone="accent">
                        <ShimmerLabel>Refreshing</ShimmerLabel>
                      </Chip>
                    )}
                  </button>
                </TableCell>
                <TableCell>{account.domain}</TableCell>
                <TableCell>
                  {account.country_code !== null ? formatCountryName(account.country_code) : "—"}
                </TableCell>
                <TableCell>{account.industry ?? "—"}</TableCell>
                <TableCell>{titleCaseEnum(account.origin)}</TableCell>
                <TableCell>
                  {account.last_refreshed_at !== null
                    ? formatRelativeDate(account.last_refreshed_at)
                    : "never"}
                </TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>

      <AccountFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
