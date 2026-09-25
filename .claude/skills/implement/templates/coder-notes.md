# Coder notes: <task title>

## Built

What was added or changed, by module, in design order.

## Documents changed

Each document and heading changed, marking requirements-register changes; the `docs/log.md` line added.

## Commands run

| Command | Result |
|---|---|
| `uv run --project scripts python scripts/check_docs.py` | 0 findings |

These are the validation commands the orchestrator and the critic re-run.

## Disputes and gaps

Where the design was wrong or silent, or where a QA test seems to contradict its criterion — quoting the criterion. "None" when there are none.

## Rounds

One entry per fix round: each QA failure and blocking finding addressed, and how.
