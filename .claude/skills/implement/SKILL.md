---
name: implement
description: Run the LeadRadar coding chain on one task - Architect, a human design approval, Coder, QA and Critic, looping until the Critic passes - on its own branch, then commit. Use when the user asks to implement requirement rows, flows or screens of the LeadRadar specification.
argument-hint: "<S-/N-/FR-/FL- ids and/or a short task description>"
disable-model-invocation: true
---

# Implement a task with the coding chain

Arguments: $ARGUMENTS

You are the orchestrator of the chain in `AGENTS.md`. You do not write code, tests, designs or reviews yourself: you prepare the task, call the agents `architect`, `coder`, `qa` and `critic` with the Agent tool one at a time (`run_in_background: false`), relay their results, ask the human where this procedure says so, and commit. Each agent starts with no memory of this conversation: everything it needs is in the task directory and in `docs/`, so prompts carry paths, never content.

Templates for the task directory are in `.claude/skills/implement/templates/`.

## 1. Prepare the task

1. Run `git status --porcelain`. If it is not empty, ask the human whether to stop or to continue on top of their changes; never stash, reset or discard them.
2. Resolve the scope from the arguments, reading `docs/requirements/traceability.md`:
   - `S-` or `N-` rows: their rows in **Requirement to acceptance**.
   - `FR-` rows or a screen name: the screen's `Obligations:` line in its feature file gives the rows; keep the `FR-` rows too.
   - `FL-` flows: their rows in **Flow coverage**.
   - Free text: search `docs/` for the rows that match, then confirm the row set with the human with AskUserQuestion before going on.
   Add every `AC-` row that verifies a row in scope. The feature slug is the feature that owns the flows or screens; when rows span features, use the one owning most of them.
3. Choose a short kebab-case slug. The task directory is `.work/<slug>/`; the branch is `<type>/<feature-slug>-<slug>`, with `feat` unless the task is a `fix`, `docs`, `test` or `chore` change (`docs/guidelines/commit-and-pr.md`). Record the base branch and `git rev-parse HEAD`.
4. Create the branch with `git switch -c <branch>`, then write `task.md` from `templates/task.md`.

## 2. Design — architect

Call the `architect` agent with: "Task directory: `.work/<slug>/`. Write `design.md`."

Read `design.md`. For every specification gap it lists, ask the human with AskUserQuestion — the design's options, its recommendation first and marked "(Recommended)" — and record each answer under **Decisions** in `task.md` with the date. If any answer was recorded, call the `architect` again: "Decisions were added to `task.md`; update `design.md`."

## 3. Approval — human

Summarise `design.md` for the human in at most 15 lines: what will be built by module, the acceptance criteria in scope and deferred, the document changes (flag requirements-register changes and ADRs), and the **Not building** list. Then ask with AskUserQuestion: **Approve**, **Change** (the human writes what to change) or **Stop**.

- Change: record the notes under **Decisions**, call the `architect` to update the design, and ask again.
- Stop: leave the branch and the task directory in place, tell the human where they are, and end.
- Approve: record the approval under **Status** in `task.md`.

## 4. Build — coder, behind the approval gate

The guard holds the coder to the phase in `.work/gate.json`, which only you write: `{"task": "<slug>", "phase": "docs"}` lets it change only `docs/`; `{"task": "<slug>", "phase": "code"}` freezes `docs/` and opens everything else; with no gate file it can write nothing but its notes.

**4a. Documents, when the design lists document changes.**

1. Write the gate with phase `docs`, then call the `coder` with: "Task directory: `.work/<slug>/`. Docs phase: apply only the document changes of the approved `design.md`, regenerate and check the bundle, and write `coder-notes.md`. Do not write code."
2. Run `git add --intent-to-add -- docs/` so new documents appear in the diff, then show the human the actual change: `git diff --stat -- docs/`, `git status --short -- docs/`, and the diff of each changed document except the generated `index.md` files and `traceability.md`. Flag requirements-register changes (`business.md`, `system.md`, `acceptance.md`, `glossary.md`) and new ADRs.
3. Ask with AskUserQuestion: **Approve the docs**, **Change** (the human writes what to change) or **Stop**. On Change, record the notes under **Decisions** and repeat from 1. On Stop, delete the gate and end as in step 3. On Approve, record under **Status** in `task.md` the approval and the output of `git diff -- docs/ | shasum`, so that the approved state is identifiable.

**4b. Code.** Write the gate with phase `code`, then call the `coder` with: "Task directory: `.work/<slug>/`. Code phase: implement the approved `design.md` against the approved documents and write `coder-notes.md`."

Read `coder-notes.md`. Disputes and gaps go to the human as in step 2. Whenever a decision — here, or later from QA or the Critic — needs a document change, go through 4a again for that change, then back to 4b with "Decisions were added to `task.md`; continue." Code never proceeds on documents a human has not approved.

## 5. Verify — qa

Call the `qa` agent with: "Task directory: `.work/<slug>/`. Write and run the acceptance and end-to-end tests for the criteria in scope in `task.md`, and write `qa-report.md`." Never mention the design, the code or the coder's notes in QA's prompt.

Read `qa-report.md`:

- **Specification findings** or `UNTESTABLE` criteria go to the human; record the decisions. A decision that changes a document goes through step 4a before QA runs again.
- `NOT RUN` for a surface the design deferred: record the deferral under **Deferred** in `task.md`. Any other `NOT RUN` counts as a failure.

## 6. Review — critic

Call the `critic` agent with: "Task directory: `.work/<slug>/`. Base commit: `<sha>`. Review the change and write `review.md`."

- `PASS`, and every criterion in scope `PASS` or recorded as deferred: go to step 8.
- `CHANGES REQUIRED`, or any QA failure: go to step 7.
- `SPEC FINDING`: ask the human, record the decision, and route it as in step 5.

## 7. Fix rounds

A round is: `coder`, with the gate in phase `code`, with "Round <n>: fix the failures in `qa-report.md` and the blocking findings in `review.md`; update `coder-notes.md`", then `qa` with "Round <n>: rerun every test for the criteria in scope and update `qa-report.md`", then `critic` as in step 6. Log each round under **Status** in `task.md`.

When `coder-notes.md` records a dispute over a QA test, show the human the criterion's words, the test's assertion and the coder's argument, ask who is right, record the answer, and tell the losing agent in its next prompt to follow the decision in `task.md`.

After 3 fix rounds, stop and show the human what still fails, asking whether to continue for another round, narrow the scope, or stop.

## 8. Finish

1. Run `uv run --project scripts python scripts/check_docs.py` and the validation commands `coder-notes.md` lists; all must pass. A failure goes back to step 7. Run `git add --intent-to-add -- docs/` and compare `git diff -- docs/ | shasum` with the last approved value in `task.md`; if it differs, the documents changed after approval — go back to step 4a before committing.
2. Commit, never including `.work/`:
   - if requirements registers changed (`docs/requirements/business.md`, `system.md`, `acceptance.md`, `glossary.md`), commit them and their generated files first as `docs(<feature-slug>): <what changed>`, naming the rows in the body;
   - then everything else as one commit `<type>(<feature-slug>): <what changed in the system>`, whose body lists the requirement rows implemented and the criteria that verify them.
   End each message with the co-author trailer your session's attribution instructions require.
3. Delete `.work/gate.json`. Update **Status** in `task.md`, then report to the human: the branch, the commits, the criteria passed and deferred, the advisory findings left open, and the next task the traceability matrix suggests. Ask before pushing or opening a pull request; never do either unasked.

## Rules

- One agent at a time, and always wait for its result.
- You write only `task.md` and `.work/gate.json`; you open the `code` phase only after a human approved the documents, or when the design lists no document change. `design.md` belongs to the architect, `coder-notes.md` to the coder, `qa-report.md` to QA and `review.md` to the critic.
- If an agent is blocked by the guard hook, never work around it; if you believe the block is wrong, tell the human.
- Every human decision goes into `task.md` under **Decisions**, dated, so that later agents and later rounds see it.
