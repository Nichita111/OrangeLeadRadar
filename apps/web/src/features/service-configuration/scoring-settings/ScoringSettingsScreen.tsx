import { useParams } from "react-router";
import { useEffect, useState } from "react";

import type { Schemas } from "../../../api/contract";
import { useIndustries, useMarkets } from "../../../api/industriesAndMarkets";
import { useScoringConfig, useScoringConfigs, useSaveScoringDraft } from "../../../api/scoring";
import { useQuestions, useService } from "../../../api/servicesAndQuestions";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { formErrors } from "../../../shell/formErrors";
import { enumLabel } from "../../../shell/format";
import { DataView } from "../../../shell/states/DataView";
import { Advanced } from "./Advanced";
import { ActivateDialog } from "./ActivateDialog";
import { BalanceAndLines } from "./BalanceAndLines";
import { Exclusions } from "./Exclusions";
import { IcpCriteria } from "./IcpCriteria";
import { draftFormFields, retiredIndustryCodes, settingsChanged } from "./scoringDraft";
import { ServiceTabs } from "../service-editor/ServiceTabs";
import { SignalsSection } from "./SignalsSection";
import { VersionsPanel } from "./VersionsPanel";

type ScoringConfigSummary = Schemas["ScoringConfigSummary"];
type ScoringSettings = Schemas["ScoringSettings"];

/**
 * [Scoring settings](/features/service-configuration.md#scoring-settings). Route
 * `/services/:id/scoring`, Admin only. WF-05.
 */
export function ScoringSettingsScreen() {
  const { id } = useParams<{ id: string }>();
  const service = useService(id);
  const configs = useScoringConfigs(id);
  const questions = useQuestions(id);
  const industries = useIndustries();
  const markets = useMarkets();

  if (id === undefined) {
    return null;
  }

  return (
    <DataView
      query={configs}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-96 w-full" />}
      empty={{ message: "", action: null }}
    >
      {(versions) => {
        const draft = versions.find((version) => version.status === "DRAFT");
        const active = versions.find((version) => version.status === "ACTIVE");
        const base = draft ?? active;
        if (base === undefined) {
          return null;
        }
        return (
          <DataView
            query={service}
            isEmpty={() => false}
            skeleton={<Skeleton className="h-8 w-64" />}
            empty={{ message: "", action: null }}
          >
            {(serviceData) => (
              <div className="flex flex-col gap-6">
                <h1 className="m-0 text-title font-semibold">{serviceData.name}</h1>
                <ServiceTabs serviceId={id} active="scoring" />
                <ScoringBody
                  serviceId={id}
                  versions={versions}
                  draft={draft}
                  active={active}
                  baseId={base.id}
                  questions={questions.data ?? []}
                  industries={industries.data ?? []}
                  markets={markets.data ?? []}
                />
              </div>
            )}
          </DataView>
        );
      }}
    </DataView>
  );
}

function ScoringBody({
  serviceId,
  versions,
  draft,
  active,
  baseId,
  questions,
  industries,
  markets,
}: {
  serviceId: string;
  versions: ScoringConfigSummary[];
  draft: ScoringConfigSummary | undefined;
  active: ScoringConfigSummary | undefined;
  baseId: string;
  questions: Schemas["SignalQuestion"][];
  industries: Schemas["Industry"][];
  markets: Schemas["Market"][];
}) {
  const [viewingId, setViewingId] = useState<string | null>(null);
  const displayedId = viewingId ?? baseId;
  const displayed = useScoringConfig(displayedId);

  return (
    <div className="grid grid-cols-[1fr_320px] gap-6">
      <DataView
        query={displayed}
        isEmpty={() => false}
        skeleton={<Skeleton className="h-96 w-full" />}
        empty={{ message: "", action: null }}
      >
        {(config) =>
          viewingId === null ? (
            <DraftEditor
              key={config.id}
              serviceId={serviceId}
              config={config}
              draft={draft}
              active={active}
              questions={questions}
              industries={industries}
              markets={markets}
            />
          ) : (
            <ReadOnlyVersion
              config={config}
              questions={questions}
              industries={industries}
              markets={markets}
              onBack={() => {
                setViewingId(null);
              }}
            />
          )
        }
      </DataView>
      <VersionsPanel versions={versions} viewingId={viewingId} onSelect={setViewingId} />
    </div>
  );
}

function ReadOnlyVersion({
  config,
  questions,
  industries,
  markets,
  onBack,
}: {
  config: Schemas["ScoringConfig"];
  questions: Schemas["SignalQuestion"][];
  industries: Schemas["Industry"][];
  markets: Schemas["Market"][];
  onBack: () => void;
}) {
  const noop = () => undefined;
  return (
    <div className="flex flex-col gap-4">
      <Callout
        kind="neutral"
        lead={`Version ${String(config.version)} (${enumLabel(config.status)})`}
      >
        Read-only.{" "}
        <button type="button" className="underline" onClick={onBack}>
          Back to draft
        </button>
        .
      </Callout>
      <fieldset disabled className="m-0 flex flex-col gap-6 border-0 p-0">
        <BalanceAndLines settings={config.settings} onChange={noop} errors={{}} />
        <IcpCriteria
          settings={config.settings}
          onChange={noop}
          industries={industries}
          markets={markets}
          errors={{}}
        />
        <SignalsSection
          settings={config.settings}
          onChange={noop}
          questions={questions}
          errors={{}}
        />
        <Exclusions settings={config.settings} onChange={noop} questions={questions} errors={{}} />
        <Advanced settings={config.settings} onChange={noop} errors={{}} hasError={false} />
      </fieldset>
    </div>
  );
}

function DraftEditor({
  serviceId,
  config,
  draft,
  active,
  questions,
  industries,
  markets,
}: {
  serviceId: string;
  config: Schemas["ScoringConfig"];
  draft: ScoringConfigSummary | undefined;
  active: ScoringConfigSummary | undefined;
  questions: Schemas["SignalQuestion"][];
  industries: Schemas["Industry"][];
  markets: Schemas["Market"][];
}) {
  const [working, setWorking] = useState<ScoringSettings>(config.settings);
  const save = useSaveScoringDraft(serviceId);
  const { notify } = useToast();
  const unsaved = settingsChanged(config.settings, working);
  // Sticky across activation: `draft` disappears from the list as soon as `API-18` succeeds
  // and the versions refetch, but the Activate dialog must stay mounted to show the queued
  // RESCORE run's progress (FR-036).
  const [activationDraftId, setActivationDraftId] = useState<string | undefined>(draft?.id);
  useEffect(() => {
    if (draft !== undefined) {
      setActivationDraftId(draft.id);
    }
  }, [draft]);
  const errors = formErrors(save.error, draftFormFields(working));
  const retired = retiredIndustryCodes(working.icp_criteria, industries);
  const hasAdvancedError = [
    "/weight_values",
    "/strength_values",
    "/default_half_life_days",
    "/min_decay",
    "/negative_factor",
    "/intent_saturation",
    "/unknown_match",
  ].some((pointer) => errors.fields[pointer] !== undefined);

  function saveDraft() {
    save.mutate(
      { settings: working },
      {
        onSuccess: () => {
          notify("Draft saved");
        },
      },
    );
  }

  const canActivate = draft !== undefined && !unsaved && retired.length === 0;
  const disabledReason = unsaved
    ? "Save the draft before activating."
    : draft === undefined
      ? "There is no draft to activate."
      : retired.length > 0
        ? "Remove the retired industries first."
        : undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2">
        {active !== undefined && <Chip tone="positive">{`v${String(active.version)} active`}</Chip>}
        {draft !== undefined && <Chip tone="caution">{`draft v${String(draft.version)}`}</Chip>}
        {unsaved && <Chip tone="cool">Unsaved changes</Chip>}
      </div>
      <BalanceAndLines settings={working} onChange={setWorking} errors={errors.fields} />
      <IcpCriteria
        settings={working}
        onChange={setWorking}
        industries={industries}
        markets={markets}
        errors={errors.fields}
      />
      <SignalsSection
        settings={working}
        onChange={setWorking}
        questions={questions}
        errors={errors.fields}
      />
      <Exclusions
        settings={working}
        onChange={setWorking}
        questions={questions}
        errors={errors.fields}
      />
      <Advanced
        settings={working}
        onChange={setWorking}
        errors={errors.fields}
        hasError={hasAdvancedError}
      />
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex items-center gap-3">
        <Button type="button" variant="primary" disabled={save.isPending} onClick={saveDraft}>
          Save draft
        </Button>
        {activationDraftId !== undefined && (
          <ActivateDialog
            serviceId={serviceId}
            draftId={activationDraftId}
            disabled={!canActivate}
            disabledReason={disabledReason}
          />
        )}
      </div>
    </div>
  );
}
