import {
  CheckIcon,
  CircleDashedIcon,
  MinusCircleIcon,
  PlusCircleIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router";

import type { Schemas } from "../../../api/contract";
import { useFindings, useRevokeOverride, type ScoreView } from "../../../api/prospectsAndEvidence";
import { useIndustries } from "../../../api/referenceData";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { countryName, enumLabel, strengthLabel } from "../../../shell/format";
import { useCurrentUser } from "../../../shell/CurrentUser";
import { RelativeTime } from "../../../shell/RelativeTime";
import { FindingQuote } from "../FindingQuote";
import { ExceptionDialog } from "./ExceptionDialog";
import { inShort } from "./inShort";

type Criterion = ScoreView["breakdown"]["fit"]["criteria"][number];

const SECTION = "flex flex-col gap-3 rounded-card border border-border bg-surface p-5";
const HEADING = "m-0 text-section font-semibold";

const MATCH_MARK = {
  MATCH: { icon: CheckIcon, label: "Matches" },
  UNKNOWN: { icon: CircleDashedIcon, label: "Unknown" },
  MISMATCH: { icon: XIcon, label: "Does not match" },
} as const;

/** The fact a criterion of each kind tests, named where its value is unknown (FR-114). */
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

/**
 * The Why tab (FR-069 to FR-071, FR-131): "In short", the Fit criteria, the counted signals, and
 * the exclusion rules with the Admin's exceptions. Everything is rendered from the score view and
 * the findings; the screen composes no score.
 */
export function WhyTab({
  account,
  score,
  serviceId,
}: {
  account: Schemas["Account"];
  score: ScoreView;
  serviceId: string;
}) {
  const isAdmin = useCurrentUser().role === "ADMIN";
  const industries = useIndustries();
  const findings = useFindings(account.id, serviceId, "ACTIVE");
  const revoke = useRevokeOverride();
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
        return enumLabel(raw);
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

  return (
    <div className="flex flex-col gap-4">
      <Callout kind="neutral" lead="In short.">
        {inShort(score, new Date())}
      </Callout>

      <section className={SECTION} aria-labelledby="why-fit">
        <h2 id="why-fit" className={HEADING}>
          Fit <span className="num">{breakdown.fit.value}</span>
        </h2>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {breakdown.fit.criteria.map((criterion) => {
            const { icon: MarkIcon, label } = MATCH_MARK[criterion.match];
            return (
              <li key={criterion.key} className="flex flex-wrap items-center gap-3">
                <MarkIcon size={20} aria-label={label} role="img" />
                <span className="font-medium">{enumLabel(criterion.key)}</span>
                <span className="text-text-secondary">{valueOf(criterion)}</span>
                <span className="text-text-tertiary">{enumLabel(criterion.weight)}</span>
                <span className="num ml-auto">{signed(criterion.points)}</span>
                {criterion.match === "UNKNOWN" && (
                  <p className="m-0 basis-full text-hint text-text-tertiary">
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
          Intent <span className="num">{breakdown.intent.value}</span>
        </h2>
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {intentEntries.map((entry) => {
            const finding = findingById.get(entry.finding_id ?? "");
            const others = findingList.filter(
              (item) => item.question.key === entry.question_key && item.id !== entry.finding_id,
            ).length;
            const PolarityIcon = entry.polarity === "POSITIVE" ? PlusCircleIcon : MinusCircleIcon;
            return (
              <li key={entry.question_key} className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-3">
                  <PolarityIcon
                    size={20}
                    weight="fill"
                    role="img"
                    aria-label={
                      entry.polarity === "POSITIVE" ? "Adds to Intent" : "Takes from Intent"
                    }
                    className={entry.polarity === "POSITIVE" ? "text-positive" : "text-negative"}
                  />
                  <span className="font-medium">{entry.question_text}</span>
                  {entry.strength !== null && (
                    <span className="text-text-secondary">{strengthLabel(entry.strength)}</span>
                  )}
                  {finding?.option != null && (
                    <span className="text-text-secondary">{finding.option.label}</span>
                  )}
                  <span className="num ml-auto">{signed(entry.points)}</span>
                </div>
                {finding !== undefined && <FindingQuote finding={finding} />}
                <div className="flex gap-4 text-hint text-text-tertiary">
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
          <Callout kind="accent" lead="Rescoring.">
            The account is being rescored with this change.
          </Callout>
        )}
        {revoke.isError && <Callout kind="error">{revoke.error.message}</Callout>}
        {matchedRules.length === 0 && (
          <p className="m-0 text-text-secondary">No exclusion rule matched.</p>
        )}
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {matchedRules.map((rule) => {
            const active = score.overrides.find(
              (item) => item.rule_key === rule.key && item.status === "ACTIVE",
            );
            const criterion = breakdown.fit.criteria.find(
              (item) => item.key === rule.criterion_key,
            );
            const signal = findingById.get(rule.finding_id ?? "");
            return (
              <li key={rule.key} className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-medium">{rule.label}</span>
                  {isAdmin && active === undefined && (
                    <ExceptionDialog
                      trigger={<Button size="small">Add exception</Button>}
                      rule={{ key: rule.key, label: rule.label }}
                      accountId={account.id}
                      serviceId={serviceId}
                      onAdded={() => {
                        setRescoring(true);
                      }}
                    />
                  )}
                  {isAdmin && active !== undefined && (
                    <ConfirmDialog
                      trigger={<Button size="small">Revoke exception</Button>}
                      title="Revoke exception"
                      description={`The rule ${active.rule_label} applies to this account again, and the account is rescored. The exception stays in the history.`}
                      confirmLabel="Revoke exception"
                      onConfirm={() => {
                        revoke.mutate(active.id, {
                          onSuccess: () => {
                            setRescoring(true);
                          },
                        });
                      }}
                    />
                  )}
                </div>
                {rule.kind === "SIGNAL" && signal !== undefined && (
                  <FindingQuote finding={signal} />
                )}
                {rule.kind === "ICP_MISMATCH" && criterion !== undefined && (
                  <p className="m-0 text-text-secondary">
                    {`${enumLabel(criterion.key)}: ${valueOf(criterion)}`}
                  </p>
                )}
                {active !== undefined && (
                  <p className="m-0 text-text-secondary">
                    Exception: {active.note}, added by {active.created_by_name}{" "}
                    <RelativeTime at={active.created_at} />.
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
