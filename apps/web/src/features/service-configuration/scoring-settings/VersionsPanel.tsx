import type { Schemas } from "../../../api/contract";
import { Chip } from "../../../components/Chip";
import { enumLabel } from "../../../shell/format";
import { RelativeTime } from "../../../shell/RelativeTime";

type ScoringConfigSummary = Schemas["ScoringConfigSummary"];

const TONE: Record<ScoringConfigSummary["status"], "positive" | "neutral" | "caution"> = {
  ACTIVE: "positive",
  DRAFT: "caution",
  RETIRED: "neutral",
};

interface VersionsPanelProps {
  versions: ScoringConfigSummary[];
  /** The version being viewed read-only, or null while editing the draft. */
  viewingId: string | null;
  onSelect: (id: string) => void;
}

/** FR-037: every version with its status, activation and change note; opens a read-only view. */
export function VersionsPanel({ versions, viewingId, onSelect }: VersionsPanelProps) {
  return (
    <div className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4">
      <h2 className="m-0 text-section font-semibold">Versions</h2>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {versions.map((version) => {
          const clickable = version.status !== "DRAFT";
          return (
            <li key={version.id}>
              <button
                type="button"
                disabled={!clickable}
                aria-current={viewingId === version.id ? "true" : undefined}
                onClick={() => {
                  onSelect(version.id);
                }}
                className="flex w-full flex-col items-start gap-1 rounded-control p-2 text-left disabled:cursor-default hover:enabled:bg-page"
              >
                <div className="flex items-center gap-2">
                  <span className="num font-medium">{`v${String(version.version)}`}</span>
                  <Chip tone={TONE[version.status]}>{enumLabel(version.status)}</Chip>
                </div>
                {version.activated_at !== null && (
                  <span className="text-hint text-text-secondary">
                    <RelativeTime at={version.activated_at} />
                    {version.activated_by_name !== null && ` · ${version.activated_by_name}`}
                  </span>
                )}
                {version.change_note !== null && (
                  <span className="text-hint text-text-secondary">{version.change_note}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
