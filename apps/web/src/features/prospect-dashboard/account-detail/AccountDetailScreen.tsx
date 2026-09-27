import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useUpdateAccount } from "../../../api/accounts";
import type { Schemas } from "../../../api/contract";
import { useIndustries } from "../../../api/industriesAndMarkets";
import { useScore } from "../../../api/prospectsAndEvidence";
import { useAccount } from "../../../api/referenceData";
import { Callout } from "../../../components/Callout";
import { Select } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { cn } from "../../../components/cn";
import { useToast } from "../../../components/Toast";
import { countryName, enumLabel } from "../../../shell/format";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";
import { BandChip } from "../BandChip";
import { ScoreFigures } from "../ScoreFigures";
import { SignalsTab } from "./SignalsTab";
import { WhyTab } from "./WhyTab";

/** The five [`account`](/architecture/sql-store.md#account) `relationship_status` values, in the
 * store's order (`FR-184`). */
const RELATIONSHIP_STATUSES: Schemas["AccountRelationshipStatus"][] = [
  "PROSPECT",
  "IN_TALKS",
  "CLIENT",
  "PAST_CLIENT",
  "DO_NOT_CONTACT",
];

const TABS = [
  { value: "why", label: "Why" },
  { value: "signals", label: "Signals" },
] as const;

/**
 * Account detail, `/accounts/:id`, with the service from the selector. WF-13, WF-14. This screen
 * builds the header, the Why tab and the Signals tab; the other tabs belong to their own features.
 */
export function AccountDetailScreen() {
  const { id = "" } = useParams();
  return <WithService>{(service) => <AccountDetail id={id} service={service} />}</WithService>;
}

function AccountDetail({ id, service }: { id: string; service: Schemas["Service"] }) {
  const [params] = useSearchParams();
  const account = useAccount(id);
  return (
    <DataView
      query={account}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-24 w-full" />}
      empty={{ message: "This account does not exist.", action: null }}
    >
      {(acc) => (
        <AccountBody
          account={acc}
          service={service}
          tab={params.get("tab") === "signals" ? "signals" : "why"}
          findingId={params.get("finding")}
        />
      )}
    </DataView>
  );
}

function AccountBody({
  account,
  service,
  tab,
  findingId,
}: {
  account: Schemas["Account"];
  service: Schemas["Service"];
  tab: "why" | "signals";
  findingId: string | null;
}) {
  const score = useScore(account.id, service.id);
  const industries = useIndustries();
  const industryLabel = industries.data?.find((item) => item.code === account.industry)?.label;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="m-0 text-title font-semibold">{account.name}</h1>
            <p className="m-0 mt-1 flex flex-wrap items-center gap-x-2 text-text-secondary">
              <a
                href={`https://${account.domain}`}
                target="_blank"
                rel="noreferrer"
                className="text-accent-ink underline"
              >
                {account.domain}
              </a>
              <span>
                {[
                  account.country_code === null ? null : countryName(account.country_code),
                  account.industry === null ? null : (industryLabel ?? account.industry),
                ]
                  .filter((part) => part !== null)
                  .join(", ")}
              </span>
              <Link to={`/accounts/${account.id}/outreach`} className="text-accent-ink underline">
                Contacts and outreach
              </Link>
              {account.parent !== null && (
                <span>
                  Parent:{" "}
                  <Link to={`/accounts/${account.parent.id}`} className="text-accent-ink underline">
                    {account.parent.name}
                  </Link>
                </span>
              )}
            </p>
          </div>
          {score.data != null && <BandChip standing={score.data.standing} band={score.data.band} />}
        </div>
        {score.data != null && (
          <>
            <ScoreFigures
              priority={score.data.priority}
              fit={score.data.fit}
              intent={score.data.intent}
            />
            <p className="m-0 text-hint text-text-tertiary">
              Scored <RelativeTime at={score.data.as_of} /> with scoring version{" "}
              {score.data.scoring_version}
            </p>
          </>
        )}
        <RelationshipStatusSelect account={account} />
      </header>

      <DataView
        query={score}
        isEmpty={(current) => current === null}
        skeleton={<Skeleton className="h-24 w-full" />}
        empty={{
          message: `Not scored yet. This account has no score for ${service.name}; it gets one at its next refresh.`,
          action: null,
        }}
      >
        {(current) =>
          current === null ? null : (
            <>
              <nav aria-label="Account detail tabs" className="flex gap-1 border-b border-border">
                {TABS.map(({ value, label }) => (
                  <Link
                    key={value}
                    to={`?tab=${value}`}
                    aria-current={tab === value ? "page" : undefined}
                    className={cn(
                      "border-b-2 px-3 py-2 font-medium",
                      tab === value
                        ? "border-accent text-accent-ink"
                        : "border-transparent text-text-secondary hover:text-text",
                    )}
                  >
                    {label}
                  </Link>
                ))}
              </nav>
              {tab === "why" ? (
                <WhyTab account={account} score={current} serviceId={service.id} />
              ) : (
                <SignalsTab accountId={account.id} serviceId={service.id} findingId={findingId} />
              )}
            </>
          )
        }
      </DataView>
    </div>
  );
}

/**
 * `FR-184`: the Relationship select, shown for every service whether or not the account has a
 * score, on every tab. Saves on selection (`FR-015`), confirms with a toast on success, and on
 * failure returns the select to the stored value and shows the error as a callout, never a toast
 * (`FR-120`).
 */
function RelationshipStatusSelect({ account }: { account: Schemas["Account"] }) {
  const update = useUpdateAccount(account.id);
  const { notify } = useToast();
  const [value, setValue] = useState(account.relationship_status);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setValue(account.relationship_status);
  }, [account.relationship_status]);

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="account-detail-relationship"
        className="flex items-center gap-2 text-hint text-text-secondary"
      >
        Relationship
        <Select
          id="account-detail-relationship"
          className="w-auto"
          value={value}
          disabled={update.isPending}
          onChange={(event) => {
            const next = event.target.value as Schemas["AccountRelationshipStatus"];
            const previous = account.relationship_status;
            setValue(next);
            setError(null);
            update.mutate(
              { relationship_status: next },
              {
                onSuccess: () => {
                  notify("Saved. The whole team shares this status; it changes no score.");
                },
                onError: (mutationError) => {
                  setValue(previous);
                  setError(mutationError.message);
                },
              },
            );
          }}
        >
          {RELATIONSHIP_STATUSES.map((status) => (
            <option key={status} value={status}>
              {enumLabel(status)}
            </option>
          ))}
        </Select>
      </label>
      {error !== null && <Callout kind="error">{error}</Callout>}
    </div>
  );
}
