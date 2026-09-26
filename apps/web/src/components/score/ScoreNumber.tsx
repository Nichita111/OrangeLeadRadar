import { cn } from "../cn";

interface ScoreNumberProps {
  label: string;
  value: number;
  /** Priority is larger than Fit and Intent (FR-112). */
  size?: "large" | "regular";
  /** A one-line meaning in words, where the number first appears on a screen. */
  meaning?: string;
}

const MAX_SCORE = 100;

/** FR-112: a score as a number in the mono face, with a bar drawn without a track. */
export function ScoreNumber({ label, value, size = "regular", meaning }: ScoreNumberProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2">
        <span className={cn("num font-semibold", size === "large" ? "text-title" : "text-section")}>
          {value}
        </span>
        <span className="text-text-secondary">{label}</span>
      </div>
      {meaning !== undefined && <span className="text-hint text-text-tertiary">{meaning}</span>}
      <div
        data-bar
        aria-hidden
        className="h-1 rounded-full bg-accent"
        style={{ width: `${String(Math.min(value, MAX_SCORE))}%` }}
      />
    </div>
  );
}
