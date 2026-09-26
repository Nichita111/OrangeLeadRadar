/**
 * The Why tab (`FR-069` to `FR-071`, `FR-131`): "In short", the Fit criteria, the counted
 * signals, and the exclusion rules with the Admin's exceptions. Everything is rendered from the
 * score view and the findings; the screen composes no score.
 */
import {
  CheckIcon,
  CircleDashedIcon,
  MinusCircleIcon,
  PlusCircleIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { Account } from "../../../api/accounts";
import { useIndustries } from "../../../api/industriesAndMarkets";
import {
  useFindings,
  useRevokeOverride,
  type FindingView,
  type Override,
  type ScoreView,
} from "../../../api/prospects";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { ConfirmDialog } from "../../../components/Dialog";
import { Quote } from "../../../components/score/Quote";
import { countryName } from "../../../shell/countries";
import {
  formatAbsoluteDateTime,
  formatRelativeDate,
  sentenceCaseKey,
  strengthLabel,
  titleCaseEnum,
} from "../../../shell/formatting";
import { useCurrentUser } from "../../../shell/current-user-context";
import { ExceptionDialog } from "./ExceptionDialog";
import { inShort } from "./inShort";

type Criterion = ScoreView["breakdown"]["fit"]["criteria"][number];

const SECTION = "flex flex-col gap-3 rounded-card border border-border bg-surface p-5";
const HEADING = "text-[15px] font-semibold text-text";

const MATCH_MARK = {
  MATCH: { icon: CheckIcon, label: "Matches" },
  UNKNOWN: { icon: CircleDashedIcon, label: "Unknown" },
  MISMATCH: { icon: XIcon, label: "Does not match" },
} as const;

/** The fact a criterion of each kind tests, named where its value is unknown (`FR-114`). */
const FACT_NAME: Record<Criterion["kind"], string> = {
  INDUSTRY: "industry",
  GEOGRAPHY: "country",
  EMPLOYEE_RANGE: "employee count",
  REVENUE_RANGE: "revenue",
  OPERATIONAL_COMPLEXITY: "operational complexity",
};

function signed(points: number): string {
  return `${points >= 0 ? "+" : ""}${points.toFixed(1)}`;
}

export function WhyTab({
  account,
  score,
  serviceId,
}: {
  account: Account;
  score: ScoreView;
  serviceId: string;
}) {
  const isAdmin = useCurrentUser().role === "ADMIN";
  const industries = useIndustries();
  const findings = useFindings(account.id, serviceId, "ACTIVE");
  const revoke = useRevokeOverride();
  const [addFor, setAddFor] = useState<{ key: string; label: string } | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<Override | null>(null);
  const [rescoring, setRescoring] = useState(false);

  const { breakdown } = score;
  const findingList = findings.data ?? [];
  const findingById = new Map(findingList.map((item) => [item.id, item]));

  const valueOf = (criterion: Criterion): string => {
    if (criterion.attribute === null) {
      return "unknown";
    }
    const raw = String(criterion.attribute);
    switch (criterion.kind) {
      case "INDUSTRY":
        return industries.data?.find((item) => item.code === raw)?.label ?? raw;
      case "GEOGRAPHY":
        return countryName(raw);
      case "OPERATIONAL_COMPLEXITY":
        return titleCaseEnum(raw);
      default:
        return raw;
    }
  };

  const counted = breakdown.intent.questions.filter((entry) => entry.finding_id !== null);
  const intentEntries = [
    ...counted.filter((entry) => entry.polarity === "POSITIVE"),
    ...counted.filter((entry) => entry.polarity === "NEGATIVE"),
  ];
  const matchedRules = breakdown.disqualifiers.filter((rule) => rule.matched);

  const quoteOf = (finding: FindingView) => (
    <Quote
      quote={finding.quote}
      quoteEn={finding.quote_en}
      url={finding.document.url}
      sourceType={finding.document.source_type}
      observedAt={finding.observed_at}
    />
  );

  return (
    <div className="flex flex-col gap-4">
      <Callout>
        <strong>In short.</strong> {inShort(score, new Date())}
      </Callout>

      <section className={SECTION} aria-labelledby="why-fit">
        <h2 id="why-fit" className={HEADING}>
          Fit <span className="font-mono">{breakdown.fit.value}</span>
        </h2>
        <ul className="flex flex-col gap-2">
          {breakdown.fit.criteria.map((criterion) => {
            const { icon: MarkIcon, label } = MATCH_MARK[criterion.match];
            return (
              <li key={criterion.key} className="flex flex-wrap items-center gap-3 text-sm">
                <MarkIcon size={20} aria-label={label} role="img" />
                <span className="font-medium text-text">{sentenceCaseKey(criterion.key)}</span>
                <span className="text-text-secondary">{valueOf(criterion)}</span>
                <span className="text-text-tertiary">{titleCaseEnum(criterion.weight)}</span>
                <span className="ml-auto font-mono">{signed(criterion.points)}</span>
                {criterion.match === "UNKNOWN" && (
                  <p className="basis-full text-[12.5px] text-text-tertiary">
                    {`Unknown: add the ${FACT_NAME[criterion.kind]} to sharpen the score.`}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className={SECTION} aria-labelledby="why-intent">
        <h2 id="why-intent" className={HEADING}>
          Intent <span className="font-mono">{breakdown.intent.value}</span>
        </h2>
        <ul className="flex flex-col gap-4">
          {intentEntries.map((entry) => {
            const finding = findingById.get(entry.finding_id ?? "");
            const others = findingList.filter(
              (item) => item.question.key === entry.question_key && item.id !== entry.finding_id,
            ).length;
            const PolarityIcon = entry.polarity === "POSITIVE" ? PlusCircleIcon : MinusCircleIcon;
            return (
              <li key={entry.question_key} className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <PolarityIcon
                    size={20}
                    weight="fill"
                    role="img"
                    aria-label={
                      entry.polarity === "POSITIVE" ? "Adds to Intent" : "Takes from Intent"
                    }
                    className={entry.polarity === "POSITIVE" ? "text-positive" : "text-negative"}
                  />
                  <span className="font-medium text-text">{entry.question_text}</span>
                  {entry.strength !== null && (
                    <span className="text-text-secondary">{strengthLabel(entry.strength)}</span>
                  )}
                  {finding?.option != null && (
                    <span className="text-text-secondary">{finding.option.label}</span>
                  )}
                  <span className="ml-auto font-mono">{signed(entry.points)}</span>
                </div>
                {finding !== undefined && quoteOf(finding)}
                <div className="flex gap-4 text-[12.5px] text-text-tertiary">
                  {others > 0 && (
                    <span>{`${String(others)} other signal${others === 1 ? "" : "s"}`}</span>
                  )}
                  <Link
                    to={`?tab=signals&finding=${entry.finding_id ?? ""}`}
                    className="text-accent-ink underline"
                  >
                    Read the evidence
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      </section>

      <section className={SECTION} aria-labelledby="why-exclusions">
        <h2 id="why-exclusions" className={HEADING}>
          Exclusions
        </h2>
        {rescoring && (
          <Callout kind="accent">
            <strong>Rescoring.</strong> The account is being rescored with this change.
          </Callout>
        )}
        {matchedRules.length === 0 && (
          <p className="text-sm text-text-secondary">No exclusion rule matched.</p>
        )}
        <ul className="flex flex-col gap-4">
          {matchedRules.map((rule) => {
            const active = score.overrides.find(
              (item) => item.rule_key === rule.key && item.status === "ACTIVE",
            );
            const criterion = breakdown.fit.criteria.find(
              (item) => item.key === rule.criterion_key,
            );
            const signal = findingById.get(rule.finding_id ?? "");
            return (
              <li key={rule.key} className="flex flex-col gap-1.5 text-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-medium text-text">{rule.label}</span>
                  {isAdmin && active === undefined && (
                    <Button
                      size="small"
                      onClick={() => {
                        setAddFor({ key: rule.key, label: rule.label });
                      }}
                    >
                      Add exception
                    </Button>
                  )}
                  {isAdmin && active !== undefined && (
                    <Button
                      size="small"
                      onClick={() => {
                        setRevokeTarget(active);
                      }}
                    >
                      Revoke exception
                    </Button>
                  )}
                </div>
                {rule.kind === "SIGNAL" && signal !== undefined && quoteOf(signal)}
                {rule.kind === "ICP_MISMATCH" && criterion !== undefined && (
                  <p className="text-text-secondary">
                    {`${sentenceCaseKey(criterion.key)}: ${valueOf(criterion)}`}
                  </p>
                )}
                {active !== undefined && (
                  <p className="text-text-secondary">
                    Exception: {active.note}, added by {active.created_by_name}{" "}
                    <span title={formatAbsoluteDateTime(active.created_at)}>
                      {formatRelativeDate(active.created_at)}
                    </span>
                    .
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {addFor !== null && (
        <ExceptionDialog
          rule={addFor}
          accountId={account.id}
          serviceId={serviceId}
          onClose={() => {
            setAddFor(null);
          }}
          onAdded={() => {
            setRescoring(true);
          }}
        />
      )}
      <ConfirmDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setRevokeTarget(null);
          }
        }}
        title="Revoke exception"
        description={`The rule ${revokeTarget?.rule_label ?? ""} applies to this account again, and the account is rescored. The exception stays in the history.`}
        confirmLabel="Revoke exception"
        confirmPending={revoke.isPending}
        error={revoke.error?.message}
        onConfirm={() => {
          if (revokeTarget === null) {
            return;
          }
          revoke.mutate(revokeTarget.id, {
            onSuccess: () => {
              setRevokeTarget(null);
              setRescoring(true);
            },
          });
        }}
      />
    </div>
  );
}
