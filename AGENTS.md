# Repository entry point

LeadRadar is specified in `docs/`, the single source of truth. Start at `docs/index.md`. Code is built from the specification by a chain of four agents; this file is their contract, and `.claude/` implements it (see [Running the chain](#running-the-chain)).

## Rules for every agent

- Read `docs/guidelines/documents/common.md` before writing or moving any document; the templates are beside it.
- A task names requirement rows (`S-XXX-nn`, `N-nn`) and, for screens, `FR-` rows. Start at the feature file that owns them (`docs/features/<slug>.md`), follow its reading order, and use `docs/requirements/traceability.md` to find the flows, tables and acceptance criteria they touch. Read only what those link to.
- Tables, enums, rules, contracts and configuration keys are each defined in exactly one place under `docs/architecture/`. Never redefine one in code comments, tests or documents; link to it.
- Behaviour the documents do not specify is a specification gap: stop and report it to a human. Never invent it in code or resolve it by reading someone else's implementation.
- A code change to a table, rule, contract or screen carries its document change in the same commit, and every change to `docs/` adds one line to `docs/log.md`.
- After changing documents run `uv run --project scripts python scripts/build_indexes.py` and `uv run --project scripts python scripts/build_traceability.py`, then `uv run --project scripts python scripts/check_docs.py`. A finding is a defect. Generated files are never edited by hand.
- Nothing ephemeral goes into `docs/`: no status marks, code line citations, to-dos or gap lists.

## The chain

```text
task ─► Architect ─► design ─► Coder ─► code + unit, integration, contract tests
                                            │
                                            ▼
                         QA ◄── acceptance criteria (never the code)
                          │  acceptance + end-to-end tests, run, report
                          ▼
                       Critic ─► findings ─► back to Coder, or to a human
```

### Architect

- **Reads**: the task's requirement rows; the owning feature's reading order; the traceability matrix rows of those requirements; the linked store tables, rules, contracts, services and decisions.
- **Produces** an implementation design in `.work/<task>/design.md`, never in `docs/`: the modules to add or change by capability; the contracts (`API-nn`), tables, rules and configuration keys involved, each by link; the order of work outside in; the unit, integration and contract tests to write; the `AC-` rows QA will cover; and every specification gap found, with a proposed document change.
- **Must not** introduce a table, column, enum value, contract, configuration key or dependency the documents do not state. When the design needs one, it proposes the document change first, with an ADR when [R7](docs/guidelines/documents/common.md) requires one.

### Coder

- **Reads**: the design and everything it links; `docs/guidelines/coding.md` and the language guideline.
- **Produces**: code and its unit, integration and contract tests, written test first; the document changes the code requires, in the same commit; a green validation of the targets it touched.
- **Must not** write acceptance or end-to-end tests, weaken or skip a test to reach green, add behaviour beyond the design, or change `docs/` outside a docs phase — nor write code before a human has approved the docs diff.

### QA

- **Reads**: only `docs/` — the `AC-` rows the traceability matrix gives for the task's requirements, the flows and screens they refer to, `docs/architecture/interfaces.md`, and the demo dataset in `docs/architecture/overview.md`. Never the implementation.
- **Produces**: one acceptance test per `AC-` row, tagged with its identifier, and end-to-end tests for the screens and scenarios involved, following `docs/guidelines/testing.md`; runs them against the composed stack in replay mode; reports each failure with its `AC-` identifier, the expected behaviour quoted from the criterion, and the observed behaviour.
- **Must not** adapt a test to match the implementation. A criterion that cannot be tested as written, or whose expected behaviour is ambiguous, is reported as a specification finding for a human.

### Critic

- **Reads**: the task, the design, the diff, the test results and the documents they link.
- **Reviews** and reports findings, each with severity (blocking or advisory), location and the rule it breaks:
  - **Overengineering and KISS** — abstractions, options, configuration, plug-in points or layers no requirement reads ([P-06](docs/architecture/overview.md)); generality beyond the task.
  - **Completeness** — every requirement of the task implemented; every `AC-` row covered by a passing test; every `FR-` row exercised; document changes, regenerated files and the `log.md` line present.
  - **DRY** — a table, enum, rule, shape or configuration key defined twice in code or documents; logic duplicated instead of invoking the rule's one implementation.
  - **Conformance** — layering, one writer per fact, pure core without I/O, no suppressions, no literal runtime numbers, no fallback results, naming from the glossary.
- **Must not** rewrite the code; it returns findings. Blocking findings go back to the Coder, specification findings to a human.

## Human decisions

A human owns: requirement registers, `draft → stable` document acceptance, ADR consolidation, specification gaps, and the release gate decision in `docs/requirements/acceptance.md`.

## Running the chain

- `/implement <rows or task>` — for example `/implement S-SCO-01 S-SCO-05` or `/implement the Prospects screen` — runs the chain on its own branch: Architect, a human approval of the design, Coder, QA, Critic, and up to three fix rounds, then commits once the Critic passes. It never pushes or opens a pull request without asking. The orchestrating procedure is `.claude/skills/implement/SKILL.md`.
- Each task keeps its working notes in `.work/<task>/`, ignored by git: `task.md` (the orchestrator's: scope, decisions, status), `design.md` (Architect), `coder-notes.md` (Coder), `qa-report.md` (QA) and `review.md` (Critic), from the templates in `.claude/skills/implement/templates/`.
- The agents are `.claude/agents/architect.md`, `coder.md`, `qa.md` and `critic.md`: Architect and Critic run on Opus, Coder and QA on Sonnet.
- Documents change before code, and code waits for a human: the Coder first works in a docs phase in which it may change only `docs/`; the orchestrator shows the human the actual docs diff, and only after approval opens the code phase, in which `docs/` is frozen. A document change discovered later goes back through the same approval. The phase lives in `.work/gate.json`, written only by the orchestrator and enforced by the guard.
- `.claude/hooks/guard.py` keeps every agent in its lane: QA cannot read `apps/`, `packages/` or the design and notes about the implementation; the Coder cannot touch `tests/acceptance/`, `tests/e2e/`, generated documents or the chain's files, and never commits; the Architect and the Critic write only their own note. `python3 .claude/hooks/test_guard.py` checks the guard.
