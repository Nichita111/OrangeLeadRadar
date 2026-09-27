import { useState, type FormEvent } from "react";
import { useParams } from "react-router";

import { useUpdateAccount } from "../../../api/accounts";
import type { Schemas } from "../../../api/contract";
import { useIndustries } from "../../../api/industriesAndMarkets";
import { useAccount } from "../../../api/referenceData";
import { useRefreshAccount } from "../../../api/runs";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { Input, Select } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";
import { enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { DataView } from "../../../shell/states/DataView";
import { ContactsSection } from "../../outreach-and-crm/ContactsSection";

type Account = Schemas["Account"];
type Complexity = Schemas["AccountOperationalComplexity"];

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";
const COMPLEXITIES: Complexity[] = ["LOW", "MEDIUM", "HIGH"];
const FIELDS = [
  "name",
  "country_code",
  "industry",
  "employee_count",
  "revenue_eur",
  "linkedin_url",
] as const;

/** S-ACC-03, S-ACC-04: Account profile, `/accounts/:id/profile`. FR-044 to FR-049. */
export function AccountProfileScreen() {
  const { id = "" } = useParams();
  const account = useAccount(id);
  return (
    <DataView
      query={account}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-96 w-full" />}
      empty={{ message: "", action: null }}
    >
      {(data) => <Profile key={data.id} account={data} />}
    </DataView>
  );
}

function OriginHint({ account, field }: { account: Account; field: string }) {
  const origin = account.attribute_origin[field];
  return origin === undefined ? null : (
    <span className="text-text-tertiary">
      {enumLabel(origin)}
      {origin === "MANUAL" ? " · never overwritten" : ""}
    </span>
  );
}

function Profile({ account }: { account: Account }) {
  const industries = useIndustries();
  const update = useUpdateAccount(account.id);
  const refresh = useRefreshAccount();
  const { notify } = useToast();
  const errors = formErrors(update.error, FIELDS);

  const [name, setName] = useState(account.name);
  const [country, setCountry] = useState(account.country_code ?? "");
  const [industry, setIndustry] = useState(account.industry ?? "");
  const [employees, setEmployees] = useState(account.employee_count?.toString() ?? "");
  const [revenue, setRevenue] = useState(account.revenue_eur?.toString() ?? "");
  const [complexity, setComplexity] = useState<Complexity | "">(
    account.operational_complexity ?? "",
  );
  const [linkedin, setLinkedin] = useState(account.linkedin_url ?? "");
  const [aliases, setAliases] = useState(account.aliases.join(", "));
  const [sources, setSources] = useState(account.sources);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body: Schemas["AccountUpdate"] = {
      ...(name !== account.name && { name }),
      ...(country !== (account.country_code ?? "") && country !== "" && { country_code: country }),
      ...(industry !== (account.industry ?? "") && industry !== "" && { industry }),
      ...(employees !== (account.employee_count?.toString() ?? "") &&
        employees !== "" && { employee_count: Number(employees) }),
      ...(revenue !== (account.revenue_eur?.toString() ?? "") &&
        revenue !== "" && { revenue_eur: Number(revenue) }),
      ...(complexity !== (account.operational_complexity ?? "") &&
        complexity !== "" && { operational_complexity: complexity }),
      ...(linkedin !== (account.linkedin_url ?? "") &&
        linkedin !== "" && { linkedin_url: linkedin }),
      ...(aliases !== account.aliases.join(", ") && {
        aliases: aliases
          .split(",")
          .map((alias) => alias.trim())
          .filter((alias) => alias !== ""),
      }),
      ...(JSON.stringify(sources) !== JSON.stringify(account.sources) && {
        sources: sources.map(({ kind, url, status }) => ({ kind, url, status })),
      }),
    };
    if (Object.keys(body).length === 0) {
      return;
    }
    update.mutate(body, {
      onSuccess: () => {
        notify("Saved. The account's scores are recomputed when an attribute changed.");
      },
    });
  };

  return (
    <>
      <PageHeader
        title={account.name}
        lead={`${account.domain} · ${enumLabel(account.origin)}${
          account.status === "INACTIVE" ? " · Inactive" : ""
        }`}
        action={
          <div className="flex gap-2">
            <ButtonLink to={`/accounts/${account.id}`}>Account detail</ButtonLink>
            <Button
              variant="primary"
              disabled={account.active_run_id !== null || refresh.isPending}
              onClick={() => {
                refresh.mutate(account.id, {
                  onSuccess: () => {
                    notify("Refresh queued. Follow it on Runs.");
                  },
                });
              }}
            >
              {account.active_run_id !== null ? "Refreshing…" : "Refresh now"}
            </Button>
          </div>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-6">
        <form
          onSubmit={submit}
          className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
        >
          <h2 className="m-0 text-section font-semibold">Profile</h2>
          <p className="m-0 text-hint text-text-tertiary">
            A value you enter here is never overwritten by Crunchbase or a suggestion.
          </p>
          <label className={LABEL}>
            Name
            <Input
              value={name}
              onChange={(event) => {
                setName(event.target.value);
              }}
            />
            {errors.fields["name"] && (
              <span className="text-negative">{errors.fields["name"]}</span>
            )}
          </label>
          <label htmlFor="accountprofile-field-156" className={LABEL}>
            Other names (comma separated)
            <Input
              id="accountprofile-field-156"
              value={aliases}
              onChange={(event) => {
                setAliases(event.target.value);
              }}
            />
          </label>
          <label htmlFor="accountprofile-field-160" className={LABEL}>
            <span>
              Country (ISO code) <OriginHint account={account} field="country_code" />
            </span>
            <Input
              id="accountprofile-field-160"
              value={country}
              maxLength={2}
              onChange={(event) => {
                setCountry(event.target.value.toUpperCase());
              }}
            />
          </label>
          <label className={LABEL}>
            <span>
              Industry <OriginHint account={account} field="industry" />
            </span>
            <Select
              value={industry}
              onChange={(event) => {
                setIndustry(event.target.value);
              }}
            >
              <option value="">Unknown</option>
              {(industries.data ?? []).map((item) => (
                <option key={item.code} value={item.code}>
                  {item.label}
                </option>
              ))}
            </Select>
          </label>
          <label htmlFor="accountprofile-field-183" className={LABEL}>
            <span>
              Employees <OriginHint account={account} field="employee_count" />
            </span>
            <Input
              id="accountprofile-field-183"
              type="number"
              min={1}
              value={employees}
              onChange={(event) => {
                setEmployees(event.target.value);
              }}
            />
          </label>
          <label htmlFor="accountprofile-field-194" className={LABEL}>
            <span>
              Revenue (EUR) <OriginHint account={account} field="revenue_eur" />
            </span>
            <Input
              id="accountprofile-field-194"
              type="number"
              min={0}
              value={revenue}
              onChange={(event) => {
                setRevenue(event.target.value);
              }}
            />
          </label>
          <label className={LABEL}>
            <span>
              Operational complexity <OriginHint account={account} field="operational_complexity" />
            </span>
            <Select
              value={complexity}
              onChange={(event) => {
                setComplexity(COMPLEXITIES.find((value) => value === event.target.value) ?? "");
              }}
            >
              <option value="">Unknown</option>
              {COMPLEXITIES.map((value) => (
                <option key={value} value={value}>
                  {enumLabel(value)}
                </option>
              ))}
            </Select>
          </label>
          <label className={LABEL}>
            LinkedIn page
            <Input
              type="url"
              value={linkedin}
              onChange={(event) => {
                setLinkedin(event.target.value);
              }}
            />
            <span className="text-text-tertiary">
              {account.linkedin_url !== null && (
                <a
                  href={account.linkedin_url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  Open in a new tab
                </a>
              )}{" "}
              LeadRadar never reads LinkedIn.
            </span>
          </label>
          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="p-0 font-medium">Sources</legend>
            {sources.length === 0 && (
              <span className="text-hint text-text-tertiary">
                No source yet; a refresh detects the website&apos;s newsroom, careers and feeds.
              </span>
            )}
            {sources.map((source, index) => (
              <label
                key={`${source.kind}-${source.url}`}
                className="flex items-center gap-2 text-hint"
              >
                <input
                  type="checkbox"
                  checked={source.status === "ACTIVE"}
                  onChange={(event) => {
                    setSources(
                      sources.map((item, i) =>
                        i === index
                          ? { ...item, status: event.target.checked ? "ACTIVE" : "INACTIVE" }
                          : item,
                      ),
                    );
                  }}
                />
                <Chip>{enumLabel(source.kind)}</Chip>
                <span className="min-w-0 truncate">{source.url}</span>
                <span className="text-text-tertiary">{enumLabel(source.origin)}</span>
              </label>
            ))}
          </fieldset>
          {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
          <div className="flex justify-end">
            <Button type="submit" variant="primary" disabled={update.isPending}>
              Save
            </Button>
          </div>
        </form>
        <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4">
          <ContactsSection accountId={account.id} />
        </section>
      </div>
      {refresh.error !== null && <Callout kind="error">{refresh.error.message}</Callout>}
    </>
  );
}
