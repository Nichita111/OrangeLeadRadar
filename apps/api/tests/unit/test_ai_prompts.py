"""Unit tests of the versioned prompts of the [OpenRouter adapter]
(/architecture/services/worker.md#ai-gateway) and of a chat request's body."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leadradar.ai.openrouter import chat_body, chat_completions_url, output_schema
from leadradar.ai.prompts import PROMPTS_DIR, load_prompt, load_prompts, render_messages
from leadradar.ai.shapes import DiscoveryInput, EvidenceOutput
from leadradar.core.enums import AiRole

pytestmark = pytest.mark.unit


def test_every_role_has_a_prompt_in_the_repository() -> None:
    prompts = load_prompts(PROMPTS_DIR)

    assert set(prompts) == set(AiRole)
    for role, prompt in prompts.items():
        assert prompt.role == role
        assert prompt.version.startswith("v")
        assert prompt.text


def test_the_highest_numbered_version_is_in_use(tmp_path: Path) -> None:
    role_dir = tmp_path / "evidence"
    role_dir.mkdir()
    for number in (1, 2, 10):
        (role_dir / f"v{number}.md").write_text(f"prompt {number}\n")
    (role_dir / "notes.md").write_text("not a version")

    prompt = load_prompt(tmp_path, AiRole.EVIDENCE)

    assert prompt.version == "v10"
    assert prompt.text == "prompt 10"


def test_a_role_without_a_prompt_fails_to_load(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt(tmp_path, AiRole.OUTREACH)


def test_the_prompt_is_the_system_message_and_the_input_the_user_message() -> None:
    prompt = load_prompt(PROMPTS_DIR, AiRole.DISCOVERY_EXTRACTION)
    role_input = DiscoveryInput(service_description="Automation", text="Ein Text", language="de")

    messages = render_messages(prompt, role_input)

    assert messages == [
        {"role": "system", "content": prompt.text},
        {
            "role": "user",
            "content": '{"service_description":"Automation","text":"Ein Text","language":"de"}',
        },
    ]


def test_a_chat_body_asks_for_structured_output_at_temperature_zero() -> None:
    prompt = load_prompt(PROMPTS_DIR, AiRole.DISCOVERY_EXTRACTION)
    role_input = DiscoveryInput(service_description="Automation", text="Text", language="en")

    body = chat_body(
        model="google/gemini-2.5-flash",
        prompt=prompt,
        role_input=role_input,
        schema_name="EvidenceOutput",
        schema=output_schema(EvidenceOutput),
    )

    assert body["model"] == "google/gemini-2.5-flash"
    assert body["temperature"] == 0
    assert body["provider"] == {"require_parameters": True}
    assert body["usage"] == {"include": True}
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    schema = response_format["json_schema"]["schema"]
    assert set(schema["required"]) == {"quote", "quote_en", "rationale"}
    assert schema["additionalProperties"] is False
    json.dumps(body)


def test_the_chat_url_is_under_the_base_url() -> None:
    assert (
        chat_completions_url("https://openrouter.ai/api/v1/")
        == "https://openrouter.ai/api/v1/chat/completions"
    )
