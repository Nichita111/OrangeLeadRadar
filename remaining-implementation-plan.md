# Remaining implementation plan

This plan finishes T04, T05, T06, T07, T10, T11, T17, T18, T19, T22 and T23 from [STATUS.md](STATUS.md).

The critical path is T10 → T11 → T07: the later work needs a refresh that produces documents, passages, findings, scores and alerts.

Two dependencies outside the requested set must also be scheduled:

- T04 cannot fully pass AC-03 without T12 reclassification.
- T07, T17 and T23 cannot fully pass their acceptance criteria without the label and quality-check work from T14.

## Wave 0 — Settle the frontend base

Resolve PR #44 before adding more screens because it rewrites the frontend foundation and changes backend contracts.

1. Rebase `feat/frontend-foundation-latest` onto current `main`.
2. Keep its frontend shell, landing page, contract tooling and demo sign-in work.
3. Take `main` for backend files and regenerate OpenAPI rather than resolving generated files manually.
4. Renumber its conflicting Landing requirements.
5. Merge or explicitly retire the branch before starting the screen work below.

## Wave 1 — Complete the P0 refresh pipeline

### PR 1: T10 FETCH stage

Implement and register the `FETCH` worker handler.

- Load the account, configured sources, active services, questions and available plug-ins.
- Run enabled free-core plug-ins and keyed plug-ins only when configured.
- Apply fetch windows, hint-term queries, quotas, rate limits, request accounting, robots rules, host delay, URL restrictions and the document cap.
- Isolate plug-in failures so one failure produces a `PARTIAL` run while other plug-ins continue.
- Write deterministic record/replay exchanges for every source call.
- Enqueue PROCESS only after all FETCH jobs reach a terminal state.
- Add integration tests for plug-in fan-out, counters, failures, quotas and replay misses.

Acceptance: AC-16, AC-30, AC-32 and AC-64.

### PR 2: T10 PROCESS stage and passage selection

Implement and register `PROCESS`.

- Extract and normalize text.
- Canonicalize URLs and detect language.
- Deduplicate by content and mark translations or near duplicates.
- Skip triage and classification for duplicates.
- Split short documents into one whole-document passage.
- Split long documents by section and preserve section paths.
- Embed every passage.
- Implement question-scoped keyword plus embedding retrieval.
- Enforce `PASSAGES_PER_QUESTION` and `MAX_PASSAGES_PER_DOCUMENT`.
- Make all writes idempotent across retries.
- Enqueue SIGNAL after processing finishes.

Acceptance: AC-17, AC-18, AC-31, AC-58, AC-71 and AC-72.

### PR 3: T11 full SIGNAL integration

Keep the existing SIGNAL implementation and connect it to T10's selected passages.

- Triage each new, non-duplicate document once.
- Classify only services retained by triage.
- Classify only the passages selected for each question.
- Preserve one classification per passage, question and revision.
- Verify escalation thresholds, evidence retries, translations, choice options, observation dates and `EVIDENCE_FAILED`.
- Reconcile or close PR #48 because its tests overlap acceptance tests already present on `main`.
- Confirm SIGNAL hands off to SCORE and reports accurate counters.
- Add full-refresh integration tests instead of testing SIGNAL only with manually inserted passages.

Acceptance: AC-20, AC-21, AC-22, AC-24 and AC-25.

### PR 4: Required T12 dependency

Merge and finish `feat/reclassify`.

- Queue RECLASSIFY when a relevant question field changes or a question is created.
- Do not queue it for hint-only changes.
- Supersede findings from older revisions.
- Reclassify only the changed question without fetching.
- Finish by rescoring the service.
- Return the run from the question API so the frontend can link to it.

Acceptance: AC-03, AC-26 and AC-73.

### PR 5: T07 deterministic demo lifecycle

Complete demo seeding after the pipeline works.

- Audit all 20 CSV rows and fill required missing employee counts, operational-complexity values and source URLs.
- Verify parent relationships, sources, services, questions, active scoring versions, ICP criteria and disqualifiers.
- Make `make seed-demo` safely repeatable and guarantee that it performs no fetch.
- Make `make refresh-demo` wait for every run and fail if any run ends unexpectedly.
- Add `make seed-labels` with stable matching from exported labels to stored passages.
- Record the demo exchanges after H2 supplies the OpenRouter configuration.
- Run two clean replay stacks and compare findings and scores.

Acceptance: AC-58 and AC-59.

`make seed-labels` and the exported label set require T14 and H5. The command can be implemented here, but T07 remains partial until that input exists.

## Wave 2 — Restore and finish the missing P0 screens

Start this wave after the frontend base is settled. Generate the API client from the current OpenAPI snapshot.

### PR 6: T04 configuration screens

Port the old Services and Service editor work from commit `1b89bfc`, adapting it to the current shell instead of copying the old application structure.

Then add the screens that were never completed:

- `/services`: list, create, deactivate and reactivate.
- `/services/:id`: overview and signal-question editor.
- `/services/:id/scoring`: draft editor, field-level JSON-pointer validation, activation and versions.
- `/settings/industries-markets`: create, rename, retire and restore.
- Show the RECLASSIFY run returned by the completed T12 API.
- Leave Try it and Preview impact for T16.

Acceptance: AC-01–AC-05 and AC-74. Exercise FR-018–FR-034, FR-036–FR-037, FR-149–FR-151 and FR-154–FR-156.

### PR 7: T05 account screens

Port the account work from commit `4254734`.

- `/accounts`: filters in the URL, search, refresh state, new-account dialog and duplicate link.
- `/accounts/import`: dry run, categorized results, confirmation, row errors and maximum-row handling.
- Account Profile tab: editable attributes, origins, aliases, sources, parent and status.
- Show the resulting RESCORE run when a score-affecting attribute changes.
- Use active industries from API-71.

Acceptance: AC-09–AC-12. Exercise FR-038–FR-048 and FR-137–FR-142.

### PR 8: T06 Runs and refresh progress

Port the Runs screen from commit `4254734` and connect it to the current shell.

- `/runs`: filters, pagination, stage, counters, errors and cancellation.
- Add Refresh now and live run progress to Account detail.
- Show done, current and pending stages and current counters.
- Preserve the same active run when refresh is requested twice.
- Verify cancellation permissions and retry/reclaim visibility.

Acceptance: AC-28, AC-30, AC-31 and AC-58.

### PR 9: T10 Source plug-ins screen

Implement `/settings/source-plugins`.

- Show key requirement/configuration, enabled state, availability and reason.
- Show usage, quotas, rate limits, last success and last error.
- Save switches and limits immediately.
- Verify Sales receives 403.

Acceptance: AC-32. Exercise FR-059–FR-061 and FR-143.

After this wave, run the complete P0 refresh flow through the UI in replay mode.

## Wave 3 — Complete the existing P1 APIs in the frontend

### PR 10: T18 feedback controls

The backend is already implemented.

- Add the lead-verdict segmented control and optional note to Account detail.
- Show verdict, actor, timestamp and the Already Customer ranking effect.
- Add Correct/Wrong controls and notes to findings.
- Show the current finding verdict and pending score update.
- Refresh the account score when the resulting RESCORE completes.

Acceptance: AC-46 and AC-47. Exercise FR-068, FR-073 and FR-133.

### PR 11: T19 History and Alerts

The history and alerts APIs and score-step alert creation already exist.

- Add the Account detail History tab.
- Render causes, scoring version/change note, before/after values, findings and exceptions.
- Add `/alerts`, defaulting to unread alerts for the selected service.
- Add unread counts to navigation.
- Open an alert at the relevant account or finding.
- Acknowledge alerts for the whole team.
- Verify repeated scoring creates no duplicate alert.

Acceptance: AC-44 and AC-45. Exercise FR-075–FR-077 and FR-134–FR-136.

## Wave 4 — Discovery, impact and operational completeness

### PR 12: T22 source detection and enrichment

Add these operations to PROCESS after basic ingestion is stable.

- Detect newsroom, investor-relations, careers and feed sources from the home page.
- Use SerpAPI only when configured.
- Never replace or duplicate manual sources.
- Fill empty attributes from Crunchbase with origin tracking.
- Classify operational complexity only when no better value exists.

Acceptance: AC-19 and AC-69.

### PR 13: T22 discovery

The command/query layer and run enqueueing already exist, but they are not exposed or executed.

- Add API-29–API-32 router models and error mappings.
- Register a DISCOVER worker handler.
- Build candidates from Crunchbase and relevant news.
- Apply ICP fit estimates, disqualifiers, existing-account checks, prior-candidate checks and the candidate cap.
- Ensure no candidate is fetched or scored before acceptance.
- Add `/suggested-accounts` with run progress, evidence, accept, reject and domain collection.
- Record a discovery replay fixture.

Acceptance: AC-14 and AC-15.

### PR 14: T14 prerequisite, T17 Impact panel and T23 escalation metric

T17 and the remaining part of T23 belong on the Quality report, which T14 owns. The smallest coherent delivery is to implement the T14 Quality report in the same program.

- Complete the quality-check worker/API and `/quality` screen.
- Calculate and store escalation rate and compare it with `ESCALATION_RATE_TARGET`.
- Add T17's Impact panel using existing API-77.
- Show accounts researched, hours replaced, refresh cost and duration, signals found, latest passing precision and label count.
- Add the required slide-ready sentence.
- Verify the release candidate passes the escalation target.

Acceptance: AC-49 and AC-75. Exercise FR-083–FR-085, FR-146–FR-148 and FR-157.

### PR 15: T23 scale-out verification

The audit log and API are already complete, so retain them and add evidence for the remaining requirement.

- Run two workers against one queue.
- Assert each job is claimed once and throughput increases.
- Configure a third service entirely through the API and refresh it without code changes.
- Add a composed-stack acceptance test for this scenario.
- Re-run AC-56 to protect the completed audit filtering.

Acceptance: AC-56 and AC-66.

## Merge and validation policy

Each PR starts from current `main`, contains one coherent capability and regenerates OpenAPI and the web client when a contract changes.

Every PR must pass:

- Ruff check and formatting.
- mypy.
- Focused unit, integration and contract tests.
- Web typecheck, lint, formatting, tests and production build when the web app changes.
- Documentation index generation, traceability generation and the documentation checker when documents change.
- Conflict-marker and generated-snapshot checks.

Before merging each wave, run the complete API suite and web validation.

At the end, run one clean composed stack in replay mode:

1. Seed an empty database.
2. Refresh all 20 accounts twice from scratch.
3. Compare findings and scores between runs.
4. Run reclassification, discovery, feedback, history, alerts, impact, audit filtering and two-worker scale-out.
5. Confirm every listed acceptance criterion passes without skips.

## Source documents

- [System requirements](docs/requirements/system.md)
- [Traceability](docs/requirements/traceability.md)
- [Acceptance criteria](docs/requirements/acceptance.md)
- [Service configuration](docs/features/service-configuration.md)
- [Accounts and discovery](docs/features/accounts-and-discovery.md)
- [Signal pipeline](docs/features/signal-pipeline.md)
- [Evaluation and feedback](docs/features/evaluation-and-feedback.md)
- [Prospect dashboard](docs/features/prospect-dashboard.md)
- [Audit trail](docs/features/audit-trail.md)
