# Architecture

* [Architecture overview](overview.md) - What LeadRadar is built from and why - principles, topology, runtime and fixture mode, store ownership, AI roles and their boundaries, degradation, the production path and the demo dataset with its seeded services and accounts.
* [SQL store](sql-store.md) - Every PostgreSQL table, column and enum of LeadRadar - identity, configuration, accounts, ingestion, signals and scores, feedback and evaluation, outreach and audit - with the scoring settings document, the audit vocabulary and the constraints.
* [Rules](rules.md) - The deterministic computations of LeadRadar - account identity, fetching, normalisation, triage, classification and escalation, evidence, the budget guard, Fit, Intent, decay, exclusion, Priority and bands, rescoring, alerts, discovery, feedback, evaluation, outreach grounding and retention - with worked scoring examples.
* [Interfaces](interfaces.md) - Every contract that crosses a boundary - the REST API the frontend calls, the in-process classifier, LLM, embedder, source plug-in and CRM ports - with every shape each carries and its source of truth.

* [Decisions](adrs/index.md) - Index of decisions
* [Services](services/index.md) - Index of services
