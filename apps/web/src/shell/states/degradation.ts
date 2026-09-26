/**
 * [Degradation](/architecture/overview.md#degradation): the dependency label and "what still
 * works" of each row, keyed by `details.dependency`
 * ([Conventions](/architecture/interfaces.md#conventions) `UPSTREAM_UNAVAILABLE`).
 */

export const DEPENDENCY_LABELS: Record<string, string> = {
  classifier: "The classifier",
  llm: "OpenRouter",
  embedder: "The embedder",
  hubspot: "HubSpot",
  database: "The database",
};

export const DEPENDENCY_STILL_WORKS: Record<string, string[]> = {
  classifier: ["Fetching and processing", "Scoring from existing findings", "Every screen"],
  llm: ["Fetching and processing", "Scoring from existing findings", "Every screen"],
  embedder: ["Scoring", "Every screen", "Preview on shorter pasted text"],
  hubspot: ["Everything else"],
  database: [],
};

export const BUDGET_EXHAUSTED_STILL_WORKS = [
  "Classification by Jev",
  "Confident negatives",
  "Scoring from existing findings",
  "Every screen",
];

/** A source plug-in's `code` is not one of the fixed dependency names above. */
export function dependencyLabel(dependency: string): string {
  return DEPENDENCY_LABELS[dependency] ?? `The ${dependency.toLowerCase()} source`;
}

export function stillWorksFor(dependency: string): string[] {
  return (
    DEPENDENCY_STILL_WORKS[dependency] ?? [
      "The other plug-ins",
      "The rest of the pipeline",
      "Every screen",
    ]
  );
}
