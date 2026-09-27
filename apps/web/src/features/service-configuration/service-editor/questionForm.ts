import type { Schemas } from "../../../api/contract";

/** The fields of a question that [`signal_question`](/architecture/sql-store.md#signal_question)
 * `revision` increments on (`API-13`'s note): `text`, `answer_type`, `options` and
 * `source_types`. `hint_terms` is not one of them. */
export interface QuestionFormShape {
  text: string;
  answer_type: Schemas["SignalQuestionAnswerType"];
  options: Schemas["QuestionOption"][] | null;
  source_types: Schemas["DocumentSourceType"][];
}

function sameOptions(
  a: Schemas["QuestionOption"][] | null,
  b: Schemas["QuestionOption"][] | null,
): boolean {
  if (a === null || b === null) {
    return a === b;
  }
  return (
    a.length === b.length &&
    a.every(
      (option, index) =>
        option.key === b[index]?.key &&
        option.label === b[index]?.label &&
        option.strength === b[index]?.strength,
    )
  );
}

function sameOrder(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

/**
 * FR-024: whether saving `edited` over `saved` will increment `revision` and re-check stored
 * data, so the form can warn before Save. Changing only `hint_terms` reads false, since it only
 * steers searching (`signal_question` `revision`).
 */
export function willIncrementRevision(
  saved: QuestionFormShape,
  edited: QuestionFormShape,
): boolean {
  return (
    saved.text !== edited.text ||
    saved.answer_type !== edited.answer_type ||
    !sameOptions(saved.options, edited.options) ||
    !sameOrder(saved.source_types, edited.source_types)
  );
}
