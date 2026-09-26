"""The [Classifier](/architecture/interfaces.md#classifier) port's two adapters, selected by
`CLASSIFIER_PROVIDER` ([ADR-02](/architecture/adrs/adr-02-classification-cascade.md)): each turns
a `ClassifierRequest` into one provider request and the provider's answer back into
`ClassifierAnswer`s. Pure: the gateway sends, records, audits and validates the port's shape with
`validate_answers`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from leadradar.ai.errors import InvalidOutput
from leadradar.ai.openrouter import chat_body, chat_completions_url, chat_content
from leadradar.ai.payload import Usage, as_object, as_probability, read_usage
from leadradar.ai.prompts import Prompt
from leadradar.ai.shapes import NO, YES, ClassifierAnswer, ClassifierQuestion, ClassifierRequest
from leadradar.core.enums import AiCallProvider, DocumentTriageClassifier, SignalQuestionAnswerType

# `API-62`: "The answer's probabilities for a question sum to 1 within 0.001".
PROBABILITY_SUM_TOLERANCE = 0.001


@dataclass(frozen=True)
class ProviderRequest:
    """One request to a provider: who serves it, where it goes and its JSON body."""

    provider: AiCallProvider
    model: str
    prompt_version: str | None
    url: str
    body: dict[str, object]


class ClassifierAdapter(Protocol):
    """One adapter of the classifier port."""

    @property
    def classifier(self) -> DocumentTriageClassifier: ...

    def build(self, request: ClassifierRequest) -> ProviderRequest: ...

    def usage(self, payload: object) -> Usage: ...

    def answers(self, request: ClassifierRequest, payload: object) -> list[ClassifierAnswer]: ...


def validate_answers(
    request: ClassifierRequest, answers: list[ClassifierAnswer]
) -> list[ClassifierAnswer]:
    """The port's shape: one answer per question, in order, over exactly the question's answer
    keys, summing to 1 within `PROBABILITY_SUM_TOLERANCE`."""
    if [answer.question_id for answer in answers] != [q.id for q in request.questions]:
        raise InvalidOutput("The answers do not match the questions asked")
    for question, answer in zip(request.questions, answers, strict=True):
        if set(answer.probabilities) != set(question.answer_keys()):
            raise InvalidOutput(f"Question {question.id} is answered over other answer values")
        if abs(sum(answer.probabilities.values()) - 1) > PROBABILITY_SUM_TOLERANCE:
            raise InvalidOutput(f"The probabilities of question {question.id} do not sum to 1")
    return answers


def _jev_question(question: ClassifierQuestion) -> dict[str, object]:
    options = question.options or []
    if question.kind == SignalQuestionAnswerType.YES_NO:
        return {"type": "noul", "instructions": question.text}
    if question.kind == SignalQuestionAnswerType.SCALE:
        return {
            "type": "score",
            "instructions": question.text,
            "criteria": [option.label for option in options],
        }
    return {
        "type": "choice",
        "instructions": question.text,
        "criteria": {option.key: option.label for option in options},
    }


def _jev_probabilities(question: ClassifierQuestion, answer: object) -> dict[str, float]:
    answer_object = as_object(answer, f"Jev's answer to {question.id}")
    if question.kind == SignalQuestionAnswerType.YES_NO:
        p_yes = as_probability(answer_object.get("noul"), f"`noul` of {question.id}")
        return {YES: p_yes, NO: 1 - p_yes}
    raw = as_object(answer_object.get("probabilities"), f"`probabilities` of {question.id}")
    keys = question.answer_keys()
    if set(raw) != set(keys) and question.kind == SignalQuestionAnswerType.SCALE:
        positions = {str(index): key for index, key in enumerate(keys)}
        if set(raw) == set(positions):
            raw = {positions[position]: value for position, value in raw.items()}
    return {
        key: as_probability(value, f"probability of {key} for {question.id}")
        for key, value in raw.items()
    }


@dataclass(frozen=True)
class JevClassifier:
    """The Jev adapter: OpenRouter's Decisions API, `JEV_MODEL`, every question in one call."""

    model: str
    decisions_url: str

    @property
    def classifier(self) -> DocumentTriageClassifier:
        return DocumentTriageClassifier.JEV

    def build(self, request: ClassifierRequest) -> ProviderRequest:
        state: object = (
            request.state
            if request.context is None
            else {"context": request.context, "text": request.state}
        )
        return ProviderRequest(
            provider=AiCallProvider.JEV,
            model=self.model,
            prompt_version=None,
            url=self.decisions_url,
            body={
                "model": self.model,
                "state": state,
                "questions": {q.id: _jev_question(q) for q in request.questions},
            },
        )

    def usage(self, payload: object) -> Usage:
        return read_usage(payload, input_key="input_tokens", output_key="output_tokens")

    def answers(self, request: ClassifierRequest, payload: object) -> list[ClassifierAnswer]:
        answers = as_object(as_object(payload, "Jev's response").get("answers"), "`answers`")
        return [
            ClassifierAnswer(
                question_id=question.id,
                probabilities=_jev_probabilities(question, answers.get(question.id)),
            )
            for question in request.questions
        ]


def llm_classifier_schema(request: ClassifierRequest) -> dict[str, object]:
    """A probability for every answer value of every question, all required."""
    return {
        "type": "object",
        "properties": {
            question.id: {
                "type": "object",
                "properties": {key: {"type": "number"} for key in question.answer_keys()},
                "required": question.answer_keys(),
                "additionalProperties": False,
            }
            for question in request.questions
        },
        "required": [question.id for question in request.questions],
        "additionalProperties": False,
    }


def _normalised(question: ClassifierQuestion, raw: object) -> dict[str, float]:
    values = as_object(raw, f"the answer to {question.id}")
    numbers: dict[str, float] = {}
    for key in question.answer_keys():
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise InvalidOutput(f"No probability of {key} for {question.id}")
        numbers[key] = float(value)
    total = sum(numbers.values())
    if total <= 0:
        raise InvalidOutput(f"The probabilities of {question.id} are all zero")
    return {key: value / total for key, value in numbers.items()}


@dataclass(frozen=True)
class LlmClassifier:
    """The LLM classifier adapter: `LLM_CLASSIFIER_MODEL` through the OpenRouter adapter, each
    question's probabilities normalised to sum to 1."""

    model: str
    openrouter_base_url: str
    prompt: Prompt

    @property
    def classifier(self) -> DocumentTriageClassifier:
        return DocumentTriageClassifier.LLM

    def build(self, request: ClassifierRequest) -> ProviderRequest:
        return ProviderRequest(
            provider=AiCallProvider.OPENROUTER,
            model=self.model,
            prompt_version=self.prompt.version,
            url=chat_completions_url(self.openrouter_base_url),
            body=chat_body(
                model=self.model,
                prompt=self.prompt,
                role_input=request,
                schema_name="classifier_answers",
                schema=llm_classifier_schema(request),
            ),
        )

    def usage(self, payload: object) -> Usage:
        return read_usage(payload, input_key="prompt_tokens", output_key="completion_tokens")

    def answers(self, request: ClassifierRequest, payload: object) -> list[ClassifierAnswer]:
        content = as_object(chat_content(payload), "The classifier's answer")
        return [
            ClassifierAnswer(
                question_id=question.id,
                probabilities=_normalised(question, content.get(question.id)),
            )
            for question in request.questions
        ]
