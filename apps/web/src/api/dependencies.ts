import type { Schemas } from "./contract";

export type Dependency = NonNullable<
  NonNullable<Schemas["ErrorEnvelope"]["error"]["details"]>["dependency"]
>;

/** The `details.dependency` values of Conventions, in the order its Dependencies table lists them. */
export const DEPENDENCIES: readonly Dependency[] = [
  "DATABASE",
  "CLASSIFIER",
  "LLM",
  "EMBEDDER",
  "HUBSPOT",
];

export function isDependency(value: unknown): value is Dependency {
  return DEPENDENCIES.some((dependency) => dependency === value);
}
