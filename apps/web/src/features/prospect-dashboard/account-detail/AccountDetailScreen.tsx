/**
 * [Account detail](/features/prospect-dashboard.md#account-detail). Route `/accounts/:id`, with
 * the service from the selector. WF-13, WF-14. This task builds the header, the Why tab and the
 * Signals tab; the other tabs belong to their own features.
 */
import { Link, useParams, useSearchParams } from "react-router-dom";

import { useAccount } from "../../../api/accounts";
import { useIndustries } from "../../../api/industriesAndMarkets";
import { useScore } from "../../../api/prospects";
import { Callout } from "../../../components/Callout";
import { BandChip } from "../../../components/score/BandChip";
import { ScoreFigures } from "../../../components/score/ScoreFigures";
import { QueryErrorState } from "../../../components/States";
import { countryName } from "../../../shell/countries";
import { formatAbsoluteDateTime, formatRelativeDate } from "../../../shell/formatting";
import { useServiceSelection } from "../../../shell/selected-service";
import { SignalsTab } from "./SignalsTab";
import { WhyTab } from "./WhyTab";

const TAB_CLASS = "border-b-2 px-3 py-2 text-sm font-medium";

export function AccountDetailScreen() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const selection = useServiceSelection();
  const { isLoading: servicesLoading, service } = selection;
  const account = useAccount(id);
  const score = useScore(id, service?.id);
  const industries = useIndustries();

  if (selection.error !== null) {
    return <QueryErrorState error={selection.error} onRetry={selection.refetch} />;
  }
  if (!servicesLoading && service === null) {
    return <p className="text-sm text-text-secondary">There is no active service yet.</p>;
  }
  if (account.isError) {
    return <QueryErrorState error={account.error} onRetry={() => void account.refetch()} />;
  }
  if (account.data === undefined || service === null) {
    return <div className="h-24 rounded-card bg-page" aria-hidden="true" />;
  }
  const { data: acc } = account;
  const tab = params.get("tab") === "signals" ? "signals" : "why";
  const industryLabel = industries.data?.find((item) => item.code === acc.industry)?.label;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-[24px] font-semibold text-text">{acc.name}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-text-secondary">
              <a
                href={`https://${acc.domain}`}
                target="_blank"
                rel="noreferrer"
                className="text-accent-ink underline"
              >
                {acc.domain}
              </a>
              <span>
                {[
                  acc.country_code === null ? null : countryName(acc.country_code),
                  acc.industry === null ? null : (industryLabel ?? acc.industry),
                ]
                  .filter((part) => part !== null)
                  .join(", ")}
              </span>
              {acc.parent !== null && (
                <span>
                  Parent:{" "}
                  <Link to={`/accounts/${acc.parent.id}`} className="text-accent-ink underline">
                    {acc.parent.name}
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
            <p className="text-[12.5px] text-text-tertiary">
              Scored{" "}
              <span title={formatAbsoluteDateTime(score.data.as_of)}>
                {formatRelativeDate(score.data.as_of)}
              </span>{" "}
              with scoring version {score.data.scoring_version}
            </p>
          </>
        )}
      </header>

      {score.isError && (
        <QueryErrorState error={score.error} onRetry={() => void score.refetch()} />
      )}
      {score.data === null && (
        <Callout>
          <strong>Not scored yet.</strong> This account has no score for {service.name}; it gets one
          at its next refresh.
        </Callout>
      )}

      {score.data != null && (
        <>
          <nav aria-label="Account detail tabs" className="flex gap-1 border-b border-border">
            {(
              [
                ["why", "Why"],
                ["signals", "Signals"],
              ] as const
            ).map(([value, label]) => (
              <Link
                key={value}
                to={`?tab=${value}`}
                aria-current={tab === value ? "page" : undefined}
                className={`${TAB_CLASS} ${
                  tab === value
                    ? "border-accent text-accent-ink"
                    : "border-transparent text-text-secondary hover:text-text"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
          {tab === "why" ? (
            <WhyTab account={acc} score={score.data} serviceId={service.id} />
          ) : (
            <SignalsTab
              accountId={acc.id}
              serviceId={service.id}
              findingId={params.get("finding")}
            />
          )}
        </>
      )}
    </div>
  );
}
