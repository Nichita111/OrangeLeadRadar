import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useAccounts, useCreateAccount, type AccountRow } from "../../../api/accounts";
import { ApiError } from "../../../api/client";
import type { Schemas } from "../../../api/contract";
import { useIndustries } from "../../../api/industriesAndMarkets";
import { useRefreshAccount } from "../../../api/runs";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { Dialog } from "../../../components/Dialog";
import { Input, Select } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { countryName, enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";
const ORIGINS: Schemas["AccountOrigin"][] = ["IMPORTED", "MANUAL", "DISCOVERED"];
const RELATIONSHIP_STATUSES: Schemas["AccountRelationshipStatus"][] = [
  "PROSPECT",
  "IN_TALKS",
  "CLIENT",
  "PAST_CLIENT",
  "DO_NOT_CONTACT",
];

/** S-ACC-01: Accounts, `/accounts`, any signed-in user. FR-038 to FR-040, FR-137, FR-138, FR-182. */
export function AccountsScreen() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<Schemas["AccountStatus"] | undefined>("ACTIVE");
  const [relationshipStatus, setRelationshipStatus] = useState<
    Schemas["AccountRelationshipStatus"] | undefined
  >(undefined);
  const [origin, setOrigin] = useState<Schemas["AccountOrigin"] | undefined>(undefined);
  const [page, setPage] = useState(1);
  const accounts = useAccounts({
    q,
    status,
    relationship_status: relationshipStatus,
    origin,
    page,
  });
  const industries = useIndustries();
  const refresh = useRefreshAccount();
  const { notify } = useToast();

  const industryLabel = (code: string | null) =>
    code === null ? "—" : (industries.data?.find((item) => item.code === code)?.label ?? code);

  return (
    <>
      <PageHeader
        title="Accounts"
        lead="The companies LeadRadar watches. Open one to see why it ranks where it does."
        action={
          <div className="flex gap-2">
            <ButtonLink to="/accounts/import">Import CSV</ButtonLink>
            <NewAccountDialog />
          </div>
        }
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label htmlFor="accounts-field-51" className={`${LABEL} min-w-64`}>
          Search
          <Input
            id="accounts-field-51"
            type="search"
            value={q}
            placeholder="Name, alias or domain"
            onChange={(event) => {
              setQ(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label htmlFor="accounts-field-63" className={LABEL}>
          Status
          <Select
            id="accounts-field-63"
            value={status ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              setStatus(value === "ACTIVE" || value === "INACTIVE" ? value : undefined);
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </Select>
        </label>
        <label className={LABEL}>
          Relationship
          <Select
            value={relationshipStatus ?? ""}
            onChange={(event) => {
              setRelationshipStatus(
                RELATIONSHIP_STATUSES.find((value) => value === event.target.value),
              );
              setPage(1);
            }}
          >
            <option value="">All</option>
            {RELATIONSHIP_STATUSES.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
        <label className={LABEL}>
          Origin
          <Select
            value={origin ?? ""}
            onChange={(event) => {
              setOrigin(ORIGINS.find((value) => value === event.target.value));
              setPage(1);
            }}
          >
            <option value="">All origins</option>
            {ORIGINS.map((value) => (
              <option key={value} value={value}>
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <DataView
        query={accounts}
        isEmpty={(data) => data.items.length === 0}
        skeleton={<Skeleton className="h-64 w-full" />}
        empty={{
          message: "No account matches. Import a CSV or add an account to start.",
          action: <ButtonLink to="/accounts/import">Import CSV</ButtonLink>,
        }}
      >
        {(data) => (
          <>
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {[
                    "Account",
                    "Country",
                    "Industry",
                    "Relationship",
                    "Origin",
                    "Last refresh",
                    "",
                  ].map(
                    (heading) => (
                      <th key={heading} scope="col" className="px-3 py-2 font-medium">
                        {heading}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {data.items.map((account: AccountRow) => (
                  <tr key={account.id} className="border-b border-border last:border-b-0">
                    <td className="px-3 py-2">
                      <Link to={`/accounts/${account.id}`} className="font-medium underline">
                        {account.name}
                      </Link>{" "}
                      {account.status === "INACTIVE" && <Chip>Inactive</Chip>}{" "}
                      {account.active_run_id !== null && <Chip tone="cool">Refreshing</Chip>}
                      <span className="block text-hint text-text-tertiary">{account.domain}</span>
                    </td>
                    <td className="px-3 py-2">
                      {account.country_code === null ? "—" : countryName(account.country_code)}
                    </td>
                    <td className="px-3 py-2">{industryLabel(account.industry)}</td>
                    <td className="px-3 py-2">{enumLabel(account.relationship_status)}</td>
                    <td className="px-3 py-2">{enumLabel(account.origin)}</td>
                    <td className="px-3 py-2 text-text-secondary">
                      {account.last_refreshed_at === null ? (
                        "Never"
                      ) : (
                        <RelativeTime at={account.last_refreshed_at} />
                      )}
                    </td>
                    <td className="flex justify-end gap-2 px-3 py-2">
                      <ButtonLink
                        size="small"
                        variant="ghost"
                        to={`/accounts/${account.id}/profile`}
                      >
                        Profile
                      </ButtonLink>
                      <Button
                        size="small"
                        variant="ghost"
                        disabled={account.active_run_id !== null || account.status === "INACTIVE"}
                        onClick={() => {
                          refresh.mutate(account.id, {
                            onSuccess: () => {
                              notify(`Refresh of ${account.name} queued`);
                            },
                          });
                        }}
                      >
                        Refresh now
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.total > data.page_size && (
              <div className="mt-3 flex items-center gap-3">
                <Button
                  size="small"
                  variant="secondary"
                  disabled={page === 1}
                  onClick={() => {
                    setPage(page - 1);
                  }}
                >
                  Previous
                </Button>
                <span className="text-hint text-text-tertiary">
                  Page {page} of {Math.ceil(data.total / data.page_size)}
                </span>
                <Button
                  size="small"
                  variant="secondary"
                  disabled={page * data.page_size >= data.total}
                  onClick={() => {
                    setPage(page + 1);
                  }}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </DataView>
      {refresh.error !== null && <Callout kind="error">{refresh.error.message}</Callout>}
    </>
  );
}

/** FR-039, FR-138: New account with domain or URL and name; a used domain links the existing one. */
function NewAccountDialog() {
  const [open, setOpen] = useState(false);
  const [domain, setDomain] = useState("");
  const [name, setName] = useState("");
  const create = useCreateAccount();
  const navigate = useNavigate();

  const conflict =
    create.error instanceof ApiError && create.error.envelope.error.code === "CONFLICT"
      ? (create.error.envelope.error.details?.["entity_id"] ?? "")
      : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (conflict) {
      void navigate(`/accounts/${conflict}`);
      return;
    }
    create.mutate(
      { domain, name, aliases: [], sources: [] },
      {
        onSuccess: (account) => {
          setOpen(false);
          void navigate(`/accounts/${account.id}/profile`);
        },
      },
    );
  };

  return (
    <Dialog
      trigger={<Button variant="primary">New account</Button>}
      title="New account"
      description="Add a company by its domain; you can fill in its profile next."
      open={open}
      onOpenChange={setOpen}
    >
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className={LABEL}>
          Domain or URL
          <Input
            required
            value={domain}
            placeholder="example.com"
            onChange={(event) => {
              setDomain(event.target.value);
              create.reset();
            }}
          />
          {conflict && (
            <span className="text-caution">
              This domain is already an account.{" "}
              <Link to={`/accounts/${conflict}`} className="underline">
                Open it
              </Link>
            </span>
          )}
        </label>
        <label htmlFor="accounts-field-263" className={LABEL}>
          Name
          <Input
            id="accounts-field-263"
            required
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </label>
        {create.error !== null && !conflict && (
          <Callout kind="error">
            {create.error instanceof ApiError
              ? create.error.envelope.error.message
              : "The account could not be created."}
          </Callout>
        )}
        <div className="flex justify-end">
          <Button type="submit" variant="primary" disabled={create.isPending}>
            {conflict ? "Open existing account" : "Create account"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
