/**
 * A neutral labelled chip, full radius per [Visual language]
 * (/architecture/services/frontend.md#visual-language). Band and standing chips belong to
 * [prospect-dashboard](/features/prospect-dashboard.md); this is the plain chip Users needs for
 * role and status, always carrying a text label so no state is colour-only (`FR-016`).
 */
export type ChipTone = "neutral" | "positive" | "caution";

const TONE_CLASSES: Record<ChipTone, string> = {
  neutral: "bg-page text-text-secondary",
  positive: "bg-positive-soft text-positive",
  caution: "bg-caution-soft text-caution",
};

export function Chip({ tone = "neutral", children }: { tone?: ChipTone; children: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[12.5px] font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}
