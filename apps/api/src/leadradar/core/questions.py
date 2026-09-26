"""Signal question shape validation (`S-CFG-02`): the `options` invariants of
[`signal_question`](/architecture/sql-store.md#signal_question) that the database's check
constraint (`options_only_for_choice`) cannot express by itself - a `CHOICE` question needs at
least two options, unique keys, and at least one of strength `NONE`."""

from __future__ import annotations

from leadradar.core.enums import FindingStrength, SignalQuestionAnswerType
from leadradar.core.scoring_settings import FieldError

MIN_CHOICE_OPTIONS = 2

_STRENGTH_VALUES = frozenset(strength.value for strength in FindingStrength)


def validate_question_shape(
    answer_type: SignalQuestionAnswerType, options: list[dict[str, object]] | None
) -> list[FieldError]:
    """Every violation of [`signal_question`](/architecture/sql-store.md#signal_question)
    `options` for the given `answer_type` (`S-CFG-02`, `FR-023`: "at least one option with
    strength None")."""
    if answer_type != SignalQuestionAnswerType.CHOICE:
        if options is not None:
            return [FieldError("/options", "Only choice questions take options.")]
        return []
    if options is None or len(options) < MIN_CHOICE_OPTIONS:
        return [
            FieldError("/options", f"Choice questions need at least {MIN_CHOICE_OPTIONS} options.")
        ]

    errors: list[FieldError] = []
    keys: list[str] = []
    strengths: list[str] = []
    for index, option in enumerate(options):
        key = option.get("key")
        if isinstance(key, str) and key:
            keys.append(key)
        else:
            errors.append(FieldError(f"/options/{index}/key", "key is required."))

        label = option.get("label")
        if not isinstance(label, str) or not label:
            errors.append(FieldError(f"/options/{index}/label", "label is required."))

        strength = option.get("strength")
        if strength in _STRENGTH_VALUES:
            strengths.append(str(strength))
        else:
            errors.append(
                FieldError(f"/options/{index}/strength", "strength must be a valid strength.")
            )

    if len(keys) != len(set(keys)):
        errors.append(FieldError("/options", "Option keys must be unique."))
    if FindingStrength.NONE.value not in strengths:
        errors.append(FieldError("/options", "At least one option must have strength NONE."))
    return errors
