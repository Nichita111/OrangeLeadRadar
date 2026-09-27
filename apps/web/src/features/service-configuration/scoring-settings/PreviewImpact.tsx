import type { Schemas } from "../../../api/contract";
import { useScoringPreview } from "../../../api/serviceConfiguration";
import { Button } from "../../../components/Button";
import { enumLabel } from "../../../shell/format";
import { PreviewErrorNotice } from "../PreviewErrorNotice";

type ScoringConfigSummary = Schemas["ScoringConfigSummary"];

function scoreLabel(score: Schemas["ScoringPreviewScore"]): string {
  const band = score.band === null ? enumLabel(score.standing) : enumLabel(score.band);
  const rank = score.rank === null ? "" : ` · #${String(score.rank)}`;
  return `${String(score.priority)} · ${band}${rank}`;
}

/** FR-035, FR-151: the impact of the saved draft, in the panel at the right of the settings. */
export function PreviewImpact({ draft }: { draft: ScoringConfigSummary | undefined }) {
  const preview = useScoringPreview();

  return (
    <section
      aria-labelledby="preview-impact-heading"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
    >
      <h2 id="preview-impact-heading" className="m-0 text-section font-semibold">
        Impact of this draft
      </h2>
      <div className="flex flex-col gap-1">
        <Button
          className="self-start"
          variant="secondary"
          disabled={draft === undefined || preview.isPending}
          onClick={() => {
            if (draft !== undefined) {
              preview.mutate(draft.id);
            }
          }}
        >
          {preview.isPending ? "Computing…" : "Preview impact"}
        </Button>
        <span className="text-hint text-text-tertiary">
          {draft === undefined
            ? "There is no saved draft to preview."
            : `Saved draft v${String(draft.version)}, nothing is written.`}
        </span>
      </div>
      {preview.error !== null && <PreviewErrorNotice error={preview.error} />}
      {preview.data !== undefined && (
        <>
          {preview.data.changes.length > 0 && (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {preview.data.changes.map((change) => (
                <li key={change.account.id} className="flex flex-col">
                  <span className="font-medium">{change.account.name}</span>
                  <span className="text-hint text-text-secondary">
                    {`${scoreLabel(change.current)} to ${scoreLabel(change.proposed)}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="m-0 text-text-secondary">
            {`${String(preview.data.unchanged_count)} accounts unchanged`}
          </p>
        </>
      )}
    </section>
  );
}
