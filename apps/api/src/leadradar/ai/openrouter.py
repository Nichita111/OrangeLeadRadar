"""The [OpenRouter adapter](/architecture/services/worker.md#ai-gateway): the body of a chat
completions request with structured output, and the reading of its answer. Pure: the gateway
sends the request."""

from __future__ import annotations

import json

from pydantic import BaseModel

from leadradar.ai.errors import InvalidOutput
from leadradar.ai.payload import as_list, as_object
from leadradar.ai.prompts import Prompt, render_messages


def chat_completions_url(openrouter_base_url: str) -> str:
    """`{OPENROUTER_BASE_URL}/chat/completions`."""
    return f"{openrouter_base_url.rstrip('/')}/chat/completions"


def chat_body(
    *,
    model: str,
    prompt: Prompt,
    role_input: BaseModel,
    schema_name: str,
    schema: dict[str, object],
) -> dict[str, object]:
    """Temperature 0, a `json_schema` response format, `provider.require_parameters` and
    `usage.include`."""
    return {
        "model": model,
        "messages": render_messages(prompt, role_input),
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "provider": {"require_parameters": True},
        "usage": {"include": True},
    }


def output_schema(output_model: type[BaseModel]) -> dict[str, object]:
    """The role's output shape as the JSON schema of its `response_format`."""
    return output_model.model_json_schema()


def chat_content(payload: object) -> object:
    """The JSON the model wrote in `choices[0].message.content`, parsed."""
    choices = as_list(as_object(payload, "The chat completion").get("choices"), "`choices`")
    if not choices:
        raise InvalidOutput("The chat completion has no choice")
    message = as_object(as_object(choices[0], "`choices[0]`").get("message"), "`message`")
    content = message.get("content")
    if not isinstance(content, str):
        raise InvalidOutput("The chat completion's content is not text")
    try:
        return json.loads(content)
    except ValueError as error:
        raise InvalidOutput("The chat completion's content is not JSON") from error
