/**
 * [Account profile](/features/accounts-and-discovery.md#account-profile). Route
 * `/accounts/:id/profile`, any signed-in user. WF-08. Contacts (`FR-048`, `FR-049`) are a
 * separate task's scope; this screen covers the account's attributes, names, sources, LinkedIn
 * field and status only.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import {
  useAccount,
  useUpdateAccount,
  type AccountSourceItem,
  type AccountSourceKind,
  type AccountStatus,
} from "../../../api/accounts";
import { useIndustries } from "../../../api/industries";
import { Button } from "../../../components/Button";
import { Input } from "../../../components/Input";
import { Select } from "../../../components/Select";
import { ErrorState, SkeletonRows, UnavailableState } from "../../../components/States";
import { Switch } from "../../../components/Switch";
import { useToast } from "../../../components/Toast";
import { formatCountryName, listCountryCodes, titleCaseEnum } from "../../../shell/formatting";
import { ApiError } from "../../../api/client";

const COUNTRY_OPTIONS = listCountryCodes();

const SOURCE_KIND_LABELS: Record<AccountSourceKind, string> = {
  WEBSITE: "Website",
  NEWSROOM: "Newsroom",
  INVESTOR_RELATIONS: "Investor relations",
  CAREERS: "Careers",
  RSS_FEED: "RSS feed",
};

/** `FR-044`: manual, Crunchbase or suggested — [Account attributes]
 * (/architecture/rules.md#account-attributes) precedence `MANUAL` > `CRUNCHBASE` > `CLASSIFIER`. */
function originLabel(origin: string | undefined): string | null {
  if (origin === "MANUAL") {
    return "manual";
  }
  if (origin === "CRUNCHBASE") {
    return "Crunchbase";
  }
  if (origin === "CLASSIFIER") {
    return "suggested";
  }
  return null;
}

interface SourceRow extends AccountSourceItem {
  removed?: boolean;
}

export function AccountProfileScreen() {
  const { id } = useParams<{ id: string }>();
  const { data: account, isLoading, isError, error, refetch } = useAccount(id);
  const { data: industries } = useIndustries();
  const updateAccount = useUpdateAccount();
  const { showToast } = useToast();

  const [countryCode, setCountryCode] = useState("");
  const [industry, setIndustry] = useState("");
  const [employeeCount, setEmployeeCount] = useState("");
  const [revenueEur, setRevenueEur] = useState("");
  const [complexity, setComplexity] = useState("");
  const [aliases, setAliases] = useState<string[]>([]);
  const [aliasDraft, setAliasDraft] = useState("");
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [status, setStatus] = useState<AccountStatus>("ACTIVE");

  useEffect(() => {
    if (account === undefined) {
      return;
    }
    setCountryCode(account.country_code ?? "");
    setIndustry(account.industry ?? "");
    setEmployeeCount(account.employee_count?.toString() ?? "");
    setRevenueEur(account.revenue_eur?.toString() ?? "");
    setComplexity(account.operational_complexity ?? "");
    setAliases(account.aliases);
    setSources(account.sources.map((source) => ({ ...source })));
    setLinkedinUrl(account.linkedin_url ?? "");
    setStatus(account.status);
  }, [account]);

  if (isLoading) {
    return <SkeletonRows rows={6} columns={1} />;
  }
  if (isError) {
    if (error instanceof ApiError && (error.status === 503 || error.status === 429)) {
      return <UnavailableState dependency="The database" stillWorks={[]} />;
    }
    return (
      <ErrorState
        message={error instanceof ApiError ? error.message : "Something went wrong."}
        onRetry={() => void refetch()}
      />
    );
  }
  if (account === undefined || id === undefined) {
    return null;
  }

  const handleSave = () => {
    updateAccount.mutate(
      {
        id: account.id,
        body: {
          country_code: countryCode.length > 0 ? countryCode : null,
          industry: industry.length > 0 ? industry : null,
          employee_count: employeeCount.length > 0 ? Number(employeeCount) : null,
          revenue_eur: revenueEur.length > 0 ? Number(revenueEur) : null,
          operational_complexity:
            complexity.length > 0 ? (complexity as "LOW" | "MEDIUM" | "HIGH") : null,
          aliases,
          sources: sources
            .filter((source) => !source.removed)
            .map((source) => ({ kind: source.kind, url: source.url, status: source.status })),
          linkedin_url: linkedinUrl.length > 0 ? linkedinUrl : null,
          status,
        },
      },
      {
        onSuccess: () => {
          showToast(`Saved. ${account.name}'s scores will be recomputed.`);
        },
        onError: (saveError) => {
          showToast(saveError instanceof ApiError ? saveError.message : "Something went wrong.");
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[24px] font-semibold text-text">
          {account.name} · {account.domain}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Edit this account's attributes, names, source addresses and status.
        </p>
      </div>

      <div className="flex flex-col gap-4 rounded-card border border-border bg-surface p-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-end gap-2">
            <Select
              id="profile-country"
              label="Country"
              value={countryCode}
              onValueChange={setCountryCode}
              options={[
                { value: "", label: "Unknown" },
                ...COUNTRY_OPTIONS.map((code) => ({ value: code, label: formatCountryName(code) })),
              ]}
            />
            {originLabel(account.attribute_origin.country_code) !== null && (
              <span className="pb-2.5 text-[12.5px] text-text-tertiary">
                {originLabel(account.attribute_origin.country_code)}
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Select
              id="profile-industry"
              label="Industry"
              value={industry}
              onValueChange={setIndustry}
              options={[
                { value: "", label: "Unknown" },
                ...(industries ?? []).map((entry) => ({ value: entry.code, label: entry.label })),
              ]}
            />
            {originLabel(account.attribute_origin.industry) !== null && (
              <span className="pb-2.5 text-[12.5px] text-text-tertiary">
                {originLabel(account.attribute_origin.industry)}
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Input
              id="profile-employees"
              label="Employees"
              inputMode="numeric"
              value={employeeCount}
              onChange={(event) => {
                setEmployeeCount(event.target.value);
              }}
            />
            {originLabel(account.attribute_origin.employee_count) !== null && (
              <span className="pb-2.5 text-[12.5px] text-text-tertiary">
                {originLabel(account.attribute_origin.employee_count)}
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Input
              id="profile-revenue"
              label="Revenue (EUR)"
              inputMode="numeric"
              value={revenueEur}
              onChange={(event) => {
                setRevenueEur(event.target.value);
              }}
            />
            {originLabel(account.attribute_origin.revenue_eur) !== null && (
              <span className="pb-2.5 text-[12.5px] text-text-tertiary">
                {originLabel(account.attribute_origin.revenue_eur)}
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Select
              id="profile-complexity"
              label="Complexity"
              value={complexity}
              onValueChange={setComplexity}
              options={[
                { value: "", label: "Unknown" },
                { value: "LOW", label: "Low" },
                { value: "MEDIUM", label: "Medium" },
                { value: "HIGH", label: "High" },
              ]}
            />
            {originLabel(account.attribute_origin.operational_complexity) !== null && (
              <span className="pb-2.5 text-[12.5px] text-text-tertiary">
                {originLabel(account.attribute_origin.operational_complexity)}
              </span>
            )}
          </div>
        </div>
        <p className="text-[12.5px] text-text-tertiary">
          A value entered here is manual: no source or suggestion ever overwrites it.
        </p>

        <div>
          <span className="text-sm font-medium text-text">Names</span>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {aliases.map((alias) => (
              <span
                key={alias}
                className="inline-flex items-center gap-1 rounded-full bg-page px-2.5 py-1 text-[12.5px] text-text"
              >
                {alias}
                <button
                  type="button"
                  aria-label={`Remove ${alias}`}
                  className="text-text-tertiary"
                  onClick={() => {
                    setAliases((current) => current.filter((entry) => entry !== alias));
                  }}
                >
                  ×
                </button>
              </span>
            ))}
            <input
              aria-label="Add a name"
              value={aliasDraft}
              onChange={(event) => {
                setAliasDraft(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && aliasDraft.trim().length > 0) {
                  event.preventDefault();
                  setAliases((current) => [...current, aliasDraft.trim()]);
                  setAliasDraft("");
                }
              }}
              placeholder="+ add a name"
              className="w-32 rounded-control border border-border bg-surface px-2 py-1 text-[12.5px] text-text"
            />
          </div>
        </div>

        <div>
          <span className="text-sm font-medium text-text">Sources</span>
          <div className="mt-1.5 flex flex-col gap-2">
            {sources
              .filter((source) => !source.removed)
              .map((source, index) => (
                <div key={`${source.kind}-${String(index)}`} className="flex items-center gap-2">
                  <span className="w-40 text-sm text-text">{SOURCE_KIND_LABELS[source.kind]}</span>
                  {source.origin === "MANUAL" ? (
                    <input
                      value={source.url}
                      onChange={(event) => {
                        const url = event.target.value;
                        setSources((current) =>
                          current.map((entry) => (entry === source ? { ...entry, url } : entry)),
                        );
                      }}
                      className="flex-1 rounded-control border border-border bg-surface px-2 py-1 text-sm text-text"
                    />
                  ) : (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 truncate text-sm text-accent"
                    >
                      {source.url}
                    </a>
                  )}
                  <span className="text-[12.5px] text-text-tertiary">
                    {source.origin === "MANUAL" ? "manual" : "detected"}
                  </span>
                  {source.origin === "DETECTED" ? (
                    <Switch
                      id={`source-${source.kind}-${String(index)}`}
                      label=""
                      checked={source.status === "ACTIVE"}
                      onCheckedChange={(checked) => {
                        setSources((current) =>
                          current.map((entry) =>
                            entry === source
                              ? { ...entry, status: checked ? "ACTIVE" : "INACTIVE" }
                              : entry,
                          ),
                        );
                      }}
                    />
                  ) : (
                    <Button
                      variant="ghost"
                      size="small"
                      aria-label={`Remove ${SOURCE_KIND_LABELS[source.kind]}`}
                      onClick={() => {
                        setSources((current) => current.filter((entry) => entry !== source));
                      }}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              ))}
          </div>
        </div>

        <div className="flex items-end gap-2">
          <Input
            id="profile-linkedin"
            label="LinkedIn"
            hint="LeadRadar never reads LinkedIn; opening the page is up to you."
            value={linkedinUrl}
            onChange={(event) => {
              setLinkedinUrl(event.target.value);
            }}
          />
          {linkedinUrl.length > 0 && (
            <a
              href={linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="pb-2.5 text-sm text-accent"
            >
              Open
            </a>
          )}
        </div>

        <fieldset className="flex items-center gap-4">
          <legend className="text-sm font-medium text-text">Status</legend>
          {(["ACTIVE", "INACTIVE"] as const).map((value) => (
            <label key={value} className="flex items-center gap-1.5 text-sm text-text">
              <input
                type="radio"
                name="account-status"
                value={value}
                checked={status === value}
                onChange={() => {
                  setStatus(value);
                }}
              />
              {titleCaseEnum(value)}
            </label>
          ))}
        </fieldset>

        <div className="flex justify-end">
          <Button variant="primary" onClick={handleSave} disabled={updateAccount.isPending}>
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
