"""Unit tests of the [Classifier](/architecture/interfaces.md#classifier) port's adapters
([AI gateway](/architecture/services/worker.md#ai-gateway)): the Jev request mapping and answer
reading, the LLM adapter's schema and normalisation, and the port's shape check."""

from __future__ import annotations

import json

import pytest

from leadradar.ai.classifier import JevClassifier, LlmClassifier, validate_answers
from leadradar.ai.errors import InvalidOutput
from leadradar.ai.prompts import PROMPTS_DIR, load_prompt
from leadradar.ai.shapes import (
    ClassifierAnswer,
    ClassifierOption,
    ClassifierQuestion,
    ClassifierRequest,
)
from leadradar.core.enums import (
    AiCallProvider,
    AiRole,
    DocumentTriageClassifier,
    SignalQuestionAnswerType,
)

pytestmark = pytest.mark.unit

LEVELS = [
    ClassifierOption(key=key, label=key.title()) for key in ("NONE", "WEAK", "MEDIUM", "STRONG")
]
REQUEST = ClassifierRequest(
    state="DHL Group announces a cost-reduction programme.",
    context="Company: DHL Group (dhl.com, DE)",
    questions=[
        ClassifierQuestion(id="q1", kind=SignalQuestionAnswerType.YES_NO, text="Cost programme?"),
        ClassifierQuestion(
            id="q2", kind=SignalQuestionAnswerType.SCALE, text="How strong?", options=LEVELS
        ),
        ClassifierQuestion(
            id="q3",
            kind=SignalQuestionAnswerType.CHOICE,
            text="Which?",
            options=[
                ClassifierOption(key="RPA", label="RPA"),
                ClassifierOption(key="NO_TOOL", label="None"),
            ],
        ),
    ],
)
JEV = JevClassifier(model="typesafe/jev-1.13", decisions_url="https://example.test/decisions")


def test_jev_maps_each_question_kind_to_its_typed_question() -> None:
    provider_request = JEV.build(REQUEST)

    assert provider_request.provider == AiCallProvider.JEV
    assert provider_request.prompt_version is None
    assert provider_request.body == {
        "model": "typesafe/jev-1.13",
        "state": {"context": "Company: DHL Group (dhl.com, DE)", "text": REQUEST.state},
        "questions": {
            "q1": {"type": "noul", "instructions": "Cost programme?"},
            "q2": {
                "type": "score",
                "instructions": "How strong?",
                "criteria": ["None", "Weak", "Medium", "Strong"],
            },
            "q3": {
                "type": "choice",
                "instructions": "Which?",
                "criteria": {"RPA": "RPA", "NO_TOOL": "None"},
            },
        },
    }


def test_jev_state_is_the_text_alone_without_a_context_line() -> None:
    request = REQUEST.model_copy(update={"context": None})

    assert JEV.build(request).body["state"] == REQUEST.state


def test_jev_answers_become_probabilities_over_the_answer_keys() -> None:
    payload = {
        "model": "typesafe/jev-1.13",
        "answers": {
            "q1": {"type": "noul", "noul": 0.8},
            "q2": {
                "type": "score",
                "score": 2,
                "probabilities": {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1},
            },
            "q3": {
                "type": "choice",
                "choice": "RPA",
                "probabilities": {"RPA": 0.7, "NO_TOOL": 0.3},
            },
        },
        "usage": {"input_tokens": 120, "output_tokens": 3, "cost": 0.0004},
    }

    answers = validate_answers(REQUEST, JEV.answers(REQUEST, payload))

    assert answers[0].probabilities == pytest.approx({"YES": 0.8, "NO": 0.2})
    assert answers[1].probabilities == {"NONE": 0.1, "WEAK": 0.2, "MEDIUM": 0.6, "STRONG": 0.1}
    assert answers[2].probabilities == {"RPA": 0.7, "NO_TOOL": 0.3}
    usage = JEV.usage(payload)
    assert (usage.input_tokens, usage.output_tokens, usage.cost_usd) == (120, 3, 0.0004)


def test_a_jev_answer_without_probabilities_is_invalid_output() -> None:
    payload = {"answers": {"q1": {"type": "noul", "noul": 0.8}, "q2": {"score": 2}, "q3": {}}}

    with pytest.raises(InvalidOutput):
        JEV.answers(REQUEST, payload)


def test_probabilities_that_do_not_sum_to_one_fail_the_port_check() -> None:
    answers = [
        ClassifierAnswer(question_id="q1", probabilities={"YES": 0.8, "NO": 0.198}),
        ClassifierAnswer(
            question_id="q2", probabilities={"NONE": 1.0, "WEAK": 0, "MEDIUM": 0, "STRONG": 0}
        ),
        ClassifierAnswer(question_id="q3", probabilities={"RPA": 0.5, "NO_TOOL": 0.5}),
    ]

    with pytest.raises(InvalidOutput):
        validate_answers(REQUEST, answers)


def test_a_sum_within_the_tolerance_passes_the_port_check() -> None:
    answers = [
        ClassifierAnswer(question_id="q1", probabilities={"YES": 0.8, "NO": 0.1995}),
        ClassifierAnswer(
            question_id="q2", probabilities={"NONE": 1.0, "WEAK": 0, "MEDIUM": 0, "STRONG": 0}
        ),
        ClassifierAnswer(question_id="q3", probabilities={"RPA": 0.5, "NO_TOOL": 0.5}),
    ]

    assert validate_answers(REQUEST, answers) == answers


def test_the_llm_classifier_requires_every_answer_value_and_normalises() -> None:
    adapter = LlmClassifier(
        model="google/gemini-2.5-flash",
        openrouter_base_url="https://example.test/api/v1",
        prompt=load_prompt(PROMPTS_DIR, AiRole.CLASSIFIER),
    )
    provider_request = adapter.build(REQUEST)
    body = json.loads(json.dumps(provider_request.body))
    schema = body["response_format"]["json_schema"]["schema"]

    assert provider_request.provider == AiCallProvider.OPENROUTER
    assert provider_request.prompt_version == "v1"
    assert adapter.classifier == DocumentTriageClassifier.LLM
    assert schema["required"] == ["q1", "q2", "q3"]
    assert schema["properties"]["q2"]["required"] == ["NONE", "WEAK", "MEDIUM", "STRONG"]

    content = {
        "q1": {"YES": 3, "NO": 1},
        "q2": {"NONE": 0.5, "WEAK": 0.5, "MEDIUM": 0, "STRONG": 0},
        "q3": {"RPA": 0.2, "NO_TOOL": 0.2},
    }
    payload = {"choices": [{"message": {"content": json.dumps(content)}}]}

    answers = validate_answers(REQUEST, adapter.answers(REQUEST, payload))

    assert answers[0].probabilities == {"YES": 0.75, "NO": 0.25}
    assert answers[2].probabilities == {"RPA": 0.5, "NO_TOOL": 0.5}


def test_an_llm_answer_missing_a_value_is_invalid_output() -> None:
    adapter = LlmClassifier(
        model="m",
        openrouter_base_url="https://example.test",
        prompt=load_prompt(PROMPTS_DIR, AiRole.CLASSIFIER),
    )
    payload = {"choices": [{"message": {"content": json.dumps({"q1": {"YES": 1}})}}]}

    with pytest.raises(InvalidOutput):
        adapter.answers(REQUEST, payload)
