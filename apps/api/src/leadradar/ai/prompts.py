"""Versioned prompts of the [OpenRouter adapter](/architecture/services/worker.md#ai-gateway):
`prompts/<role>/v<n>.md`, `<role>` the AI role in lower case, the highest `n` in use. The prompt
is the system message; the user message is the role's input shape as JSON. Rendering is pure;
only `load_prompts` reads files, once, when the gateway is built."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from leadradar.core.enums import AiRole

# src/leadradar/ai/prompts.py → apps/api/prompts, the directory the product image copies too.
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"

_VERSION_FILE = re.compile(r"^v(\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    """One role's prompt in use: its `prompt_version` (`v<n>`) and text."""

    role: AiRole
    version: str
    text: str


def load_prompt(prompts_dir: Path, role: AiRole) -> Prompt:
    """The highest-numbered `v<n>.md` of the role's directory; raises when there is none."""
    role_dir = prompts_dir / role.value.lower()
    versions = [
        (int(match.group(1)), path)
        for path in (role_dir.iterdir() if role_dir.is_dir() else [])
        if (match := _VERSION_FILE.match(path.name))
    ]
    if not versions:
        raise FileNotFoundError(f"No prompt v<n>.md in {role_dir}")
    number, path = max(versions)
    return Prompt(role=role, version=f"v{number}", text=path.read_text(encoding="utf-8").strip())


def load_prompts(prompts_dir: Path = PROMPTS_DIR) -> dict[AiRole, Prompt]:
    """Every role's prompt in use."""
    return {role: load_prompt(prompts_dir, role) for role in AiRole}


def render_messages(prompt: Prompt, role_input: BaseModel) -> list[dict[str, str]]:
    """The chat messages of one call: the prompt as system message, the input as JSON."""
    return [
        {"role": "system", "content": prompt.text},
        {"role": "user", "content": role_input.model_dump_json()},
    ]
