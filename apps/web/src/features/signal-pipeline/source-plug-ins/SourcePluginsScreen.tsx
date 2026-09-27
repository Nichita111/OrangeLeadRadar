import { useEffect, useRef, useState } from "react";

import { ApiError } from "../../../api/client";
import type { Schemas } from "../../../api/contract";
import { useSourcePlugins, useUpdateSourcePlugin, type SourcePlugin } from "../../../api/runs";
import { Callout } from "../../../components/Callout";
import { Chip, type ChipTone } from "../../../components/Chip";
import { Input } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { Switch } from "../../../components/Switch";
import { useToast } from "../../../components/Toast";
import { enumLabel } from "../../../shell/format";
import { formErrors } from "../../../shell/formErrors";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { availability, keyNote, type Availability } from "./availability";
import { WHAT_IT_READS } from "./pluginWords";

const COLUMNS = [
  "Plug-in",
  "Needs key",
  "Key",
  "Enabled",
  "Availability",
  "Today / quota",
  "Per minute",
  "Last success",
  "Last error",
];

const TONE: Record<Availability["kind"], ChipTone> = {
  AVAILABLE: "positive",
  SWITCHED_OFF: "neutral",
  KEY_MISSING: "caution",
  QUOTA_REACHED: "caution",
};

const CHIP_TEXT: Record<Availability["kind"], string> = {
  AVAILABLE: "Available",
  SWITCHED_OFF: "Switched off",
  KEY_MISSING: "Unavailable: key missing",
  QUOTA_REACHED: "Unavailable: daily quota reached",
};

// FR-060: shown under the Availability chip whenever the plug-in needs a key it does not have.
const KEY_MISSING_NOTE =
  "Stays unavailable until the key is set in the deployment's configuration.";

const EMPTY_RATE_LIMIT_MESSAGE = "A per-minute limit cannot be empty.";
const FORM_FIELDS = ["enabled", "daily_quota", "rate_limit_per_minute"] as const;

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-14 w-full" />
      ))}
    </div>
  );
}

/** "GDELT switched off", "NewsAPI daily quota saved" (FR-061, FR-120). */
function saveMessage(plugin: SourcePlugin, body: Schemas["SourcePluginUpdate"]): string {
  const label = enumLabel(plugin.code);
  if (body.enabled !== undefined) {
    return `${label} switched ${body.enabled ? "on" : "off"}`;
  }
  if (body.daily_quota !== undefined) {
    return `${label} daily quota saved`;
  }
  return `${label} per-minute limit saved`;
}

function stringOf(value: number | null): string {
  return value === null ? "" : String(value);
}

interface LimitInputProps {
  value: number | null;
  label: string;
  nullable: boolean;
  error: string | undefined;
  disabled: boolean;
  onSave: (value: number | null) => void;
}

/**
 * `FR-061`, G4: a limit's draft is local until it loses focus or Enter is pressed, and only saved
 * when it changed; Escape restores the contract's value. An empty, non-nullable value (the
 * per-minute limit) is refused on the client and never sent.
 */
function LimitInput({ value, label, nullable, error, disabled, onSave }: LimitInputProps) {
  const [draft, setDraft] = useState(() => stringOf(value));
  const [localError, setLocalError] = useState<string | undefined>(undefined);

  useEffect(() => {
    setDraft(stringOf(value));
    setLocalError(undefined);
  }, [value]);

  function commit() {
    const trimmed = draft.trim();
    if (trimmed === "") {
      if (!nullable) {
        setLocalError(EMPTY_RATE_LIMIT_MESSAGE);
        return;
      }
      if (value !== null) {
        onSave(null);
      }
      return;
    }
    const parsed = Number(trimmed);
    if (Number.isNaN(parsed)) {
      setLocalError("Enter a number.");
      return;
    }
    setLocalError(undefined);
    if (parsed !== value) {
      onSave(parsed);
    }
  }

  const shownError = localError ?? error;
  return (
    <div className="flex flex-col gap-1">
      <Input
        type="number"
        aria-label={label}
        aria-invalid={shownError !== undefined ? true : undefined}
        className="w-24"
        value={draft}
        disabled={disabled}
        onChange={(event) => {
          setDraft(event.target.value);
          setLocalError(undefined);
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur();
          } else if (event.key === "Escape") {
            setDraft(stringOf(value));
            setLocalError(undefined);
          }
        }}
      />
      {shownError !== undefined && <span className="text-hint text-negative">{shownError}</span>}
    </div>
  );
}

interface PluginRowProps {
  plugin: SourcePlugin;
  pending: boolean;
  errors: Partial<Record<string, string>>;
  onSave: (body: Schemas["SourcePluginUpdate"]) => void;
}

function PluginRow({ plugin, pending, errors, onSave }: PluginRowProps) {
  const label = enumLabel(plugin.code);
  const kind = availability(plugin).kind;
  return (
    <tr className="border-b border-border align-top last:border-b-0">
      <td className="px-4 py-3">
        <div className="font-medium">{label}</div>
        <div className="mt-0.5 max-w-xs text-hint text-text-secondary">
          {WHAT_IT_READS[plugin.code]}
        </div>
      </td>
      <td className="px-4 py-3">{plugin.needs_key ? "yes" : "no"}</td>
      <td className="px-4 py-3">
        {plugin.needs_key ? (plugin.key_configured ? "set" : "missing") : "—"}
      </td>
      <td className="px-4 py-3">
        <Switch
          checked={plugin.enabled}
          disabled={pending}
          label={`Enabled, ${label}`}
          onChange={(next) => {
            onSave({ enabled: next });
          }}
        />
      </td>
      <td className="px-4 py-3">
        <Chip tone={TONE[kind]}>{CHIP_TEXT[kind]}</Chip>
        {keyNote(plugin) && (
          <p className="m-0 mt-1 max-w-xs text-hint text-text-secondary">{KEY_MISSING_NOTE}</p>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <span className="num text-text-secondary">{plugin.requests_today}</span>
          <span className="text-text-tertiary">/</span>
          <LimitInput
            value={plugin.daily_quota}
            label={`Daily quota, ${label}`}
            nullable
            error={errors["daily_quota"]}
            disabled={pending}
            onSave={(next) => {
              onSave({ daily_quota: next });
            }}
          />
        </div>
      </td>
      <td className="px-4 py-3">
        <LimitInput
          value={plugin.rate_limit_per_minute}
          label={`Requests per minute, ${label}`}
          nullable={false}
          error={errors["rate_limit_per_minute"]}
          disabled={pending}
          onSave={(next) => {
            if (next !== null) {
              onSave({ rate_limit_per_minute: next });
            }
          }}
        />
      </td>
      <td className="px-4 py-3 text-text-secondary">
        {plugin.last_success_at === null ? "Never" : <RelativeTime at={plugin.last_success_at} />}
      </td>
      <td className="px-4 py-3 text-text-secondary">
        {plugin.last_error === null ? (
          "—"
        ) : (
          <span className="flex flex-col gap-0.5">
            <span>{plugin.last_error}</span>
            {plugin.last_error_at !== null && <RelativeTime at={plugin.last_error_at} />}
          </span>
        )}
      </td>
    </tr>
  );
}

/**
 * `WF-11`, `FR-059` to `FR-061`, `FR-143`, `S-ING-01`, `S-PIP-05`: lists every source plug-in with
 * its key need, switch, availability, usage against its limits, and the last fetch's outcome. The
 * switch and either limit save immediately through `API-38` (`AC-32`).
 */
export function SourcePluginsScreen() {
  const plugins = useSourcePlugins();
  const update = useUpdateSourcePlugin();
  const { notify } = useToast();
  const [saveError, setSaveError] = useState<Error | null>(null);
  // The plug-in whose last save answered VALIDATION, so only that row shows the field errors of
  // the mutation's current `error`.
  const [fieldErrorCode, setFieldErrorCode] = useState<Schemas["SourcePluginCode"] | null>(null);
  const lastErrorRef = useRef<Error | null>(null);

  function save(plugin: SourcePlugin, body: Schemas["SourcePluginUpdate"]) {
    setSaveError(null);
    setFieldErrorCode(null);
    update.mutate(
      { code: plugin.code, body },
      {
        onSuccess: () => {
          notify(saveMessage(plugin, body));
        },
        onError: (error) => {
          lastErrorRef.current = error;
          if (error instanceof ApiError && error.envelope.error.code === "VALIDATION") {
            setFieldErrorCode(plugin.code);
          } else {
            setSaveError(error);
          }
        },
      },
    );
  }

  const fieldErrors =
    fieldErrorCode === null ? {} : formErrors(lastErrorRef.current, FORM_FIELDS).fields;

  return (
    <>
      <PageHeader
        title="Source plug-ins"
        lead="See what each source reads, whether it can run now, and adjust its switch and limits."
      />
      {saveError !== null && <Callout kind="error">{saveError.message}</Callout>}
      <DataView
        query={plugins}
        isEmpty={(rows) => rows.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No plug-ins yet. They are created when the database is seeded.",
          action: null,
        }}
      >
        {(rows) => (
          <div className="flex flex-col gap-3">
            <div className="overflow-hidden rounded-card border border-border bg-surface">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-border text-hint text-text-tertiary">
                    {COLUMNS.map((column) => (
                      <th key={column} scope="col" className="px-4 py-3 font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((plugin) => (
                    <PluginRow
                      key={plugin.code}
                      plugin={plugin}
                      pending={update.isPending && update.variables.code === plugin.code}
                      errors={fieldErrorCode === plugin.code ? fieldErrors : {}}
                      onSave={(body) => {
                        save(plugin, body);
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="m-0 text-hint text-text-tertiary">
              An empty daily quota means no limit. Each save applies from the next fetch.
            </p>
          </div>
        )}
      </DataView>
    </>
  );
}
