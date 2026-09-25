---
type: Feature
title: Evaluation and feedback
description: How feedback on leads and signals corrects scores and becomes labelled data, how the team labels passages blind, and how an Admin runs a quality check that measures precision, recall, escalation and calibration against the release gate.
status: draft
tags: [evaluation-and-feedback]
---

# Evaluation and feedback

## Purpose

Signal accuracy is what the product is judged on, so it is measured, not assumed. The team builds a labelled set by judging passages against questions without seeing the classifier's answer; signal feedback from daily use adds to it. A quality check replays the classification cascade over the set and reports precision, recall, how often the LLM was needed and how well confidences match reality, and it passes only at `EVAL_MIN_PRECISION` over at least `EVAL_MIN_ITEMS` labels. The same numbers decide whether Jev or the LLM classifier is configured and where the escalation band sits. Feedback also has an immediate effect: a signal marked wrong stops counting and a customer leaves the ranking.

## Flows

### FL-15 Give feedback on a lead or a signal

```mermaid
sequenceDiagram
  actor Sales
  participant Web as Account detail
  participant API as api
  participant DB as database
  participant W as worker
  Sales->>Web: Wrong on a signal (or a lead verdict)
  Web->>API: finding feedback (API-47) or lead feedback (API-46)
  API->>DB: feedback row; finding REJECTED; label FINDING_FEEDBACK unless a manual label exists; RESCORE run
  W->>DB: rescore the account for the service
  Web->>API: score view (API-40)
  API-->>Web: Intent without the rejected signal
```

1. A verdict on a signal is recorded; `WRONG` takes the signal out of scoring and `CORRECT` restores it ([Feedback effects](/architecture/rules.md#feedback-effects)).
2. Unless someone labelled that passage and question by hand, the verdict also becomes a label.
3. A lead verdict of Already a customer takes the account out of the ranking for that service; Relevant and Not relevant are recorded for the quality report.

### FL-16 Label passages and run a quality check

1. A team member opens [Labelling](#labelling) and gets passages paired with questions, drawn across low, uncertain and high classifier confidence without being shown which.
2. They judge each pair as no signal, weak, clear or strong, or skip it (`API-51`).
3. An Admin opens the [Quality report](#quality-report) and runs a quality check (`API-53`); the worker replays classification and escalation over the active labels and stores the metrics.
4. The report shows whether the release gate passes, the classifier alone against the full cascade, per-question results, calibration and the misclassified pairs; the Admin adjusts questions or the configured classifier and runs again.

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Lead feedback, Finding feedback, Evaluation item, Evaluation run, Label queue, Precision, Recall, Escalation rate, Calibration, Release gate, Strength.
2. Requirement rows: `S-EVL-01` to `S-EVL-05`, `S-SIG-04` in [system requirements](/requirements/system.md); `N-03`; `B-24`, `B-27`, `B-28`, `B-40` in [business requirements](/requirements/business.md).
3. Stores: [`lead_feedback`](/architecture/sql-store.md#lead_feedback), [`finding_feedback`](/architecture/sql-store.md#finding_feedback), [`evaluation_item`](/architecture/sql-store.md#evaluation_item), [`evaluation_result`](/architecture/sql-store.md#evaluation_result), [`finding`](/architecture/sql-store.md#finding), [`chunk`](/architecture/sql-store.md#chunk).
4. Rules: [Feedback effects](/architecture/rules.md#feedback-effects), [Evaluation metrics](/architecture/rules.md#evaluation-metrics) with its label queue, [Signal classification](/architecture/rules.md#signal-classification), [Escalation](/architecture/rules.md#escalation), [Rescoring](/architecture/rules.md#rescoring), [Impact](/architecture/rules.md#impact).
5. Interfaces: [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts) (`API-46`, `API-47`), [Evaluation](/architecture/interfaces.md#evaluation) (`API-50` to `API-55`, `API-77`), [Classifier](/architecture/interfaces.md#classifier).
6. Services: the [api](/architecture/services/api.md) (`LABEL_QUEUE_SIZE`); the [worker](/architecture/services/worker.md) (`EVAL_MIN_PRECISION`, `EVAL_MIN_ITEMS`, `ESCALATION_LOWER`, `ESCALATION_UPPER`, `ESCALATION_RATE_TARGET`, `CLASSIFIER_PROVIDER` in its [runtime](/architecture/services/worker.md#runtime)); the [frontend](/architecture/services/frontend.md) shell; [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries).
7. Decisions: [ADR-14](/architecture/adrs/adr-14-labelled-set-and-precision-gate.md), [ADR-02](/architecture/adrs/adr-02-classification-cascade.md), [ADR-06](/architecture/adrs/adr-06-rule-based-scoring-with-versioned-settings.md), [ADR-15](/architecture/adrs/adr-15-openrouter-as-the-llm-provider.md).
8. Screens: [Labelling](#labelling), [Quality report](#quality-report); the feedback controls live on [Account detail](/features/prospect-dashboard.md#account-detail).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-21`, `AC-23`, `AC-46` to `AC-49`, `AC-58`, `AC-75`.

## Labelling

Route `/labelling`. Any signed-in user; uses the selected service.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Labelling · Intelligent Automation        Labels: 143 of 200 needed          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Question  Does the company announce or run a cost-reduction, efficiency or   │
│           profitability programme?                                           │
│ Company   Lufthansa Group                                                    │
│ Source    "Lufthansa Group streamlines administration" · lufthansagroup.com ↗ │
│           English · 4 months ago                                             │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ By 2030 the Group plans to reduce around 4,000 administrative positions  │ │
│ │ through digitalisation, automation and the consolidation of processes…   │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ Does this passage show it?  [0 No] [1 Weak] [2 Clear] [3 Strong]   [S Skip]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-17 — Labelling

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-078` | The screen shall show one task at a time — the question, the company, the source with its link, language and age, and the passage in its original language, with no translation offered (labellers may use the browser's own) — and never the classifier's answer. |
| `FR-079` | The answer buttons shall be No, Weak, Clear and Strong, operable with the keys 0 to 3, and Skip with S; answering saves the label and shows the next task. |
| `FR-080` | The header shall show the number of active labels against `EVAL_MIN_ITEMS`. |
| `FR-081` | When the queue is empty the screen shall say so and suggest refreshing more accounts. |
| `FR-144` | The header shall show a progress bar of the active labels against `EVAL_MIN_ITEMS`, and a callout shall say that the classifier's answer is never shown. |
| `FR-145` | A legend under the answer buttons shall say in one line what No, Weak, Clear and Strong each mean, and answering shall confirm with a toast before the next task appears. |

Obligations: `S-EVL-03`.

**Data**: `API-50`, `API-51`. **States**: [States](/architecture/services/frontend.md#states).

## Quality report

Route `/quality`. Admin only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Quality report                                     [ Run quality check ]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Latest: 2026-09-24 · classifier JEV · 214 labels        ✔ PASSES the gate    │
│ Precision 0.86 (gate 0.80)   Recall 0.71   Strength agreement 0.64          │
│ Escalated 12 % (target ≤ 15 %)   Classifier alone: precision 0.78 recall 0.69 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Per question        Labels  Precision  Recall                                │
│ COST_PROGRAM        41      0.91       0.80                                  │
│ AUTOMATION_HIRING   28      0.75       0.60                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Calibration  [ bar chart: predicted confidence vs share actually positive ]  │
│ Mistakes     expected Clear · predicted No · p 0.41 · escalated   [ open ]   │
│ Lead verdicts by band   Hot: 9 relevant / 1 not   Warm: 6 / 4   Cold: 1 / 7   │
│ History  2026-09-24 JEV pass 0.86 · 2026-09-22 LLM fail 0.77                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

WF-18 — Quality report

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-082` | Run quality check shall start an evaluation run and show its progress; while one runs the button shows it. |
| `FR-083` | The latest result shall show pass or fail against the gate with the gate's values, precision, recall, strength agreement, escalation rate against `ESCALATION_RATE_TARGET`, the classifier-alone precision and recall, the classifier evaluated and the escalation band used. |
| `FR-084` | The report shall show per-question and per-source-type results, the share of labelled passages the selection leaves unread that hold a signal, a calibration chart of mean predicted confidence against the observed share of positives per bin, the misclassified pairs with a link to each passage, and lead verdicts by band. |
| `FR-157` | An Impact panel shall show, for the last `IMPACT_PERIOD_DAYS`, the accounts researched and the hours of manual research that replaces — naming `MANUAL_RESEARCH_MINUTES_PER_ACCOUNT` as the team's assumption — the AI cost and minutes per refresh, the signals found, and the latest passing precision with its label count, closing with one sentence a slide can quote. |
| `FR-085` | History shall list earlier quality checks with date, classifier, labels, precision and pass or fail, and open any of them. |
| `FR-146` | The latest result shall open with one sentence saying whether the release gate passes, and each metric shall carry a one-line meaning in words. |
| `FR-147` | A question whose precision is below the gate shall be flagged in the per-question table, with a callout suggesting to reword it in the Service editor and run another quality check. |
| `FR-148` | The calibration chart shall say how to read it, and lead verdicts by band shall be paired bars of relevant and not relevant with their counts. |

Obligations: `S-EVL-04`, `S-EVL-05`, `N-03`.

**Data**: `API-52`, `API-53`, `API-54`, `API-55`, `API-77`, `API-35`. **States**: [States](/architecture/services/frontend.md#states).

## Open questions

- Who labels the first 200 pairs, and whether two people should label the same pairs to measure agreement. Decides: the team lead.
