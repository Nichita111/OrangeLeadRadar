# LeadRadar

LeadRadar is an AI-powered B2B sales-signal platform built for the Orange Systems hackathon challenge. It gathers public information about target accounts, asks each service's configurable signal questions of every relevant passage, keeps every positive answer as a finding with a verbatim quote, and ranks the accounts with an explainable Fit, Intent and Priority score.

The product is specified before it is built: [`docs/`](docs/index.md) is the single source of truth, and code is written from it by the agent chain in [`AGENTS.md`](AGENTS.md). This README only points into the specification; when the two disagree, the specification wins.

## Architecture

![LeadRadar architecture](diagrams/svg/architecture.svg)

Two processes share one PostgreSQL store: the **api** answers the React app and makes the interactive AI calls, and the **worker** claims jobs from the database to fetch, embed, classify and score. Models answer questions and write text; deterministic rules compute every score. Details: [architecture overview](docs/architecture/overview.md), [SQL store](docs/architecture/sql-store.md), [rules](docs/architecture/rules.md), [interfaces](docs/architecture/interfaces.md) and the [decision records](docs/architecture/adrs/index.md).

## Flows

One diagram per flow of the specification, `FL-01` to `FL-22`, grouped by feature. Each shows the participants and messages its flow heading describes, with the contracts (`API-nn`) it uses. Expand a flow to see it.

### Service configuration

Specified in [`docs/features/service-configuration.md`](docs/features/service-configuration.md).

<details>
<summary><b>FL-01</b> Define a service and its signal questions</summary>

[Spec](docs/features/service-configuration.md#fl-01-define-a-service-and-its-signal-questions)

![FL-01 Define a service and its signal questions](diagrams/svg/fl-01.svg)

</details>

<details>
<summary><b>FL-02</b> Edit and activate scoring settings</summary>

[Spec](docs/features/service-configuration.md#fl-02-edit-and-activate-scoring-settings)

![FL-02 Edit and activate scoring settings](diagrams/svg/fl-02.svg)

</details>

<details>
<summary><b>FL-03</b> Try a question</summary>

[Spec](docs/features/service-configuration.md#fl-03-try-a-question)

![FL-03 Try a question](diagrams/svg/fl-03.svg)

</details>

<details>
<summary><b>FL-22</b> Maintain industries and markets</summary>

[Spec](docs/features/service-configuration.md#fl-22-maintain-industries-and-markets)

![FL-22 Maintain industries and markets](diagrams/svg/fl-22.svg)

</details>

### Accounts and discovery

Specified in [`docs/features/accounts-and-discovery.md`](docs/features/accounts-and-discovery.md).

<details>
<summary><b>FL-04</b> Import accounts from a CSV file</summary>

[Spec](docs/features/accounts-and-discovery.md#fl-04-import-accounts-from-a-csv-file)

![FL-04 Import accounts from a CSV file](diagrams/svg/fl-04.svg)

</details>

<details>
<summary><b>FL-05</b> Maintain an account and its contacts</summary>

[Spec](docs/features/accounts-and-discovery.md#fl-05-maintain-an-account-and-its-contacts)

![FL-05 Maintain an account and its contacts](diagrams/svg/fl-05.svg)

</details>

<details>
<summary><b>FL-06</b> Discover and accept suggested accounts</summary>

[Spec](docs/features/accounts-and-discovery.md#fl-06-discover-and-accept-suggested-accounts)

![FL-06 Discover and accept suggested accounts](diagrams/svg/fl-06.svg)

</details>

### Signal pipeline

Specified in [`docs/features/signal-pipeline.md`](docs/features/signal-pipeline.md).

<details>
<summary><b>FL-07</b> Refresh one account</summary>

[Spec](docs/features/signal-pipeline.md#fl-07-refresh-one-account)

![FL-07 Refresh one account](diagrams/svg/fl-07.svg)

</details>

<details>
<summary><b>FL-08</b> Scheduled refresh cycle</summary>

[Spec](docs/features/signal-pipeline.md#fl-08-scheduled-refresh-cycle)

![FL-08 Scheduled refresh cycle](diagrams/svg/fl-08.svg)

</details>

<details>
<summary><b>FL-09</b> Reclassify after a question change</summary>

[Spec](docs/features/signal-pipeline.md#fl-09-reclassify-after-a-question-change)

![FL-09 Reclassify after a question change](diagrams/svg/fl-09.svg)

</details>

<details>
<summary><b>FL-10</b> Rescore after a scoring or data change</summary>

[Spec](docs/features/signal-pipeline.md#fl-10-rescore-after-a-scoring-or-data-change)

![FL-10 Rescore after a scoring or data change](diagrams/svg/fl-10.svg)

</details>

### Prospect dashboard

Specified in [`docs/features/prospect-dashboard.md`](docs/features/prospect-dashboard.md).

<details>
<summary><b>FL-11</b> Work the prospect list</summary>

[Spec](docs/features/prospect-dashboard.md#fl-11-work-the-prospect-list)

![FL-11 Work the prospect list](diagrams/svg/fl-11.svg)

</details>

<details>
<summary><b>FL-12</b> Explain a lead</summary>

[Spec](docs/features/prospect-dashboard.md#fl-12-explain-a-lead)

![FL-12 Explain a lead](diagrams/svg/fl-12.svg)

</details>

<details>
<summary><b>FL-13</b> Override a disqualifier</summary>

[Spec](docs/features/prospect-dashboard.md#fl-13-override-a-disqualifier)

![FL-13 Override a disqualifier](diagrams/svg/fl-13.svg)

</details>

<details>
<summary><b>FL-14</b> Act on an alert</summary>

[Spec](docs/features/prospect-dashboard.md#fl-14-act-on-an-alert)

![FL-14 Act on an alert](diagrams/svg/fl-14.svg)

</details>

### Evaluation and feedback

Specified in [`docs/features/evaluation-and-feedback.md`](docs/features/evaluation-and-feedback.md).

<details>
<summary><b>FL-15</b> Give feedback on a lead or a signal</summary>

[Spec](docs/features/evaluation-and-feedback.md#fl-15-give-feedback-on-a-lead-or-a-signal)

![FL-15 Give feedback on a lead or a signal](diagrams/svg/fl-15.svg)

</details>

<details>
<summary><b>FL-16</b> Label passages and run a quality check</summary>

[Spec](docs/features/evaluation-and-feedback.md#fl-16-label-passages-and-run-a-quality-check)

![FL-16 Label passages and run a quality check](diagrams/svg/fl-16.svg)

</details>

### Outreach and CRM

Specified in [`docs/features/outreach-and-crm.md`](docs/features/outreach-and-crm.md).

<details>
<summary><b>FL-17</b> Draft outreach</summary>

[Spec](docs/features/outreach-and-crm.md#fl-17-draft-outreach)

![FL-17 Draft outreach](diagrams/svg/fl-17.svg)

</details>

<details>
<summary><b>FL-18</b> Push to HubSpot</summary>

[Spec](docs/features/outreach-and-crm.md#fl-18-push-to-hubspot)

![FL-18 Push to HubSpot](diagrams/svg/fl-18.svg)

</details>

### Identity and access

Specified in [`docs/features/identity-and-access.md`](docs/features/identity-and-access.md).

<details>
<summary><b>FL-19</b> Sign in and sign out</summary>

[Spec](docs/features/identity-and-access.md#fl-19-sign-in-and-sign-out)

![FL-19 Sign in and sign out](diagrams/svg/fl-19.svg)

</details>

<details>
<summary><b>FL-20</b> Manage users</summary>

[Spec](docs/features/identity-and-access.md#fl-20-manage-users)

![FL-20 Manage users](diagrams/svg/fl-20.svg)

</details>

### Audit trail

Specified in [`docs/features/audit-trail.md`](docs/features/audit-trail.md).

<details>
<summary><b>FL-21</b> Review the audit trail</summary>

[Spec](docs/features/audit-trail.md#fl-21-review-the-audit-trail)

![FL-21 Review the audit trail](diagrams/svg/fl-21.svg)

</details>

## Diagrams

The diagrams are generated with [Archify](https://github.com/tt-a1i/archify) 2.17.0-dev.1 from the sources in [`diagrams/src/`](diagrams/src/):

- `diagrams/svg/` holds the static, dual-theme images shown above; they follow the reader's light or dark preference.
- `diagrams/html/` receives the interactive versions, with pan, zoom, search, focus and export. They are build output: git ignores them, so generate them to browse locally.

The diagrams are not read from the specification: [`diagrams/flows.py`](diagrams/flows.py) restates each flow by hand, and [`architecture.json`](diagrams/src/architecture.json) restates the [Topology](docs/architecture/overview.md#topology) of the architecture overview. `flows.py` records a fingerprint of the specification text each diagram was last checked against, so a diagram a specification change leaves behind shows up:

```bash
python3 diagrams/flows.py --check
```

It lists every diagram whose flow heading or topology changed since. Update that diagram's entry in `flows.py` (or `architecture.json`), record the fingerprint the check prints in `REVIEWED`, then regenerate:

```bash
python3 diagrams/flows.py
```

```bash
for f in diagrams/src/*.json; do n=$(basename "$f" .json); t=sequence; [ "$n" = architecture ] && t=architecture; node <archify>/bin/archify.mjs deliver "$t" "$f" "diagrams/html/$n.html" --quality showcase; done
```

```bash
node diagrams/export-svg.mjs <archify> diagrams/html diagrams/svg
```

`<archify>` is the Archify skill directory. Every diagram must pass Archify's `showcase` validation.

## Repository

| Path | What it holds |
|---|---|
| [`docs/`](docs/index.md) | The specification: requirements, architecture, features, guidelines and the challenge brief |
| [`AGENTS.md`](AGENTS.md) | The Architect, Coder, QA and Critic chain that builds code from the specification |
| [`.claude/`](.claude/) | The chain's agents, guard hook and `/implement` skill |
| [`scripts/`](scripts/) | The documentation checker and generators |
| [`diagrams/`](diagrams/) | Architecture and flow diagrams |

Check the specification after changing it, and whether a diagram now lags behind it:

```bash
uv run --project scripts python scripts/check_docs.py
```

```bash
python3 diagrams/flows.py --check
```
