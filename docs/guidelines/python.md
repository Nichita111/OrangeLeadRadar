---
type: Guideline
title: Python guidelines
description: How Python spells the coding guidelines for the api and the worker - toolchain and package layout, style, FastAPI, Pydantic, SQLAlchemy and Alembic, async, LangGraph and the AI gateway, and tests.
status: draft
tags: []
---

# Python guidelines

The api and the worker are one Python package, `leadradar`, with two entry points. This file says how the [coding guidelines](/guidelines/coding.md) are spelled in Python.

## Toolchain

- Python 3.12, managed with `uv`; one `pyproject.toml` and lockfile for the package.
- `ruff` for linting and formatting, `mypy --strict` for types, `pytest` for tests.
- *planned*: `uv run poe validate` runs format check, lint, type check, the import-boundary check and every test level the package owns.

## Package layout

```
apps/api/
├── pyproject.toml
├── alembic/                    migrations: the only way the schema changes
├── prompts/<role>/v<n>.md      versioned prompts of the AI gateway
├── src/leadradar/
│   ├── core/                   pure rules: identity, normalisation, routing, decay, scoring, validation
│   ├── db/                     SQLAlchemy models, one per table of the SQL store, and session handling
│   ├── api/                    FastAPI app, one router module per interface family, error mapping
│   ├── <capability>/           one package per capability: its functions, queries and errors
│   ├── ai/                     AI gateway: classifier port and adapters, LLM adapter, budget guard, fixtures
│   ├── plugins/                source plug-in adapters and the shared HTTP client
│   └── worker/                 job loop, scheduler, stages, signal graph
└── tests/                      unit/, integration/, contract/ — never inside src/
```

`core` imports nothing from `db`, `api`, `ai`, `plugins` or `worker`, and no I/O library; an import-boundary check enforces it.

## Style

- `from __future__ import annotations` in every module; absolute imports only.
- Closed sets are `enum.StrEnum` whose values are the store's enum values.
- Configuration is one `pydantic-settings` class per process, read once at start and passed in; no module reads the environment.
- Logging with the standard library, formatted as JSON lines with `request_id` or `run_id`; never log a password, token, API key or contact name.
- Time is `datetime` in UTC with timezone; a function that needs "now" takes it as an argument.

## FastAPI

- One router per interface family; a route's path, method and roles match its contracts row exactly.
- Request and response bodies are Pydantic models named after the shapes of [interfaces](/architecture/interfaces.md).
- Authentication and the role check are dependencies applied per router; the CSRF check is middleware.
- Errors are raised as typed exceptions and mapped by one exception handler to the envelope.

## Pydantic

- Models at boundaries only: request, response, settings, the AI gateway's structured outputs. Inside, use dataclasses or plain values.
- `model_config = ConfigDict(extra="forbid", frozen=True)` for inputs, so an unknown field such as a contact's email is refused.
- The [scoring settings document](/architecture/sql-store.md#scoring-settings-document) is one Pydantic model; [Scoring settings validation](/architecture/rules.md#scoring-settings-validation) is a pure function over it that returns every violation with its JSON pointer.

## SQLAlchemy and Alembic

- SQLAlchemy 2 typed declarative models, async sessions over `psycopg` 3; `pgvector`'s SQLAlchemy type for embeddings.
- One transaction per request or job step, opened by the capability function.
- Idempotent writes use `INSERT … ON CONFLICT` against the unique constraints of the store.
- Job claiming uses `SELECT … FOR UPDATE SKIP LOCKED`.
- Every schema change is an Alembic migration, reviewed with the store document change.

## Async

The api and the worker are async end to end: FastAPI async routes, async sessions, `httpx.AsyncClient` for every outbound call. Concurrency of AI calls is bounded by a semaphore sized by `AI_CONCURRENCY`. CPU-heavy parsing — PDF text extraction — runs in a worker thread.

## AI gateway and LangGraph

- Every classifier and LLM call goes through the gateway's port functions; nothing else imports a provider SDK.
- Structured output is requested with a tool whose JSON schema is generated from the Pydantic output model.
- The signal graph is one `StateGraph` module; its nodes are thin functions calling `core` rules and the gateway, and each writes its results before returning.

## Tests

- `pytest` with markers `unit` (default, sockets disabled), `integration` (a real PostgreSQL with `pgvector` through testcontainers) and `contract`.
- Table-driven tests with `pytest.mark.parametrize` for the pure rules; the [rules examples](/architecture/rules.md#examples) are unit tests too.
- A provider is never called from a test: adapters are tested against recorded fixtures.
