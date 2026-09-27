import type { Schemas } from "../api/contract";

/**
 * Every value of a wire enum, in the order it is offered, typed against the generated schema
 * (`satisfies`) so a new contract value fails typecheck here instead of being silently missing
 * from a control. One list per enum ([coding](/guidelines/coding.md), AGENTS "defined in exactly
 * one place"); every screen that offers the enum imports from here.
 */

export const WEIGHT_LEVELS = ["HIGH", "MEDIUM", "LOW", "NONE"] satisfies Schemas["WeightLevel"][];

/** [`signal_question`](/architecture/sql-store.md#signal_question) `options[].strength` and
 * `finding.strength`, weakest first. */
export const FINDING_STRENGTHS = [
  "NONE",
  "WEAK",
  "MEDIUM",
  "STRONG",
] satisfies Schemas["FindingStrength"][];

/** Every strength but `NONE`: a `Disqualifier.min_strength` choice (`FR-032`), and
 * `strength_values`' three keys (`FR-033`). `NONE` would exclude nothing, and is not a
 * `strength_values` key. */
export const STRENGTHS_ABOVE_NONE = FINDING_STRENGTHS.filter(
  (strength): strength is Exclude<Schemas["FindingStrength"], "NONE"> => strength !== "NONE",
);

export const DOCUMENT_SOURCE_TYPES = [
  "NEWS",
  "COMPANY_PUBLICATION",
  "JOB_POSTING",
  "COMPANY_PROFILE",
] satisfies Schemas["DocumentSourceType"][];

export const SIGNAL_QUESTION_ANSWER_TYPES = [
  "YES_NO",
  "SCALE",
  "CHOICE",
] satisfies Schemas["SignalQuestionAnswerType"][];
