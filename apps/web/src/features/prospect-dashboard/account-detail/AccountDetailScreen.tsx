import { Link, useParams, useSearchParams } from "react-router";

import type { Schemas } from "../../../api/contract";
import { useScore } from "../../../api/prospectsAndEvidence";
import { useAccount, useIndustries } from "../../../api/referenceData";
import { Skeleton } from "../../../components/Skeleton";
import { cn } from "../../../components/cn";
import { countryName } from "../../../shell/format";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";
import { BandChip } from "../BandChip";
import { ScoreFigures } from "../ScoreFigures";
import { SignalsTab } from "./SignalsTab";
import { WhyTab } from "./WhyTab";

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
