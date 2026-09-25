---
okf_version: "0.2"
---

# LeadRadar

* [Update log](log.md) - What changed in this bundle, newest first

# Reference

* [LeadRadar challenge brief](reference/challenge-brief.md) - The hackathon brief as received - problem statement, challenge, solution scope, data sources, expected stack, prizes and judging criteria.
* [Annex 1 Participant Reference Pack](reference/annex-1-participant-reference-pack.md) - The brief's annex as received - the current manual sales process for Intelligent Automation and the Lufthansa and DHL illustrative examples.

# Guidelines

* [Coding guidelines](guidelines/coding.md) - How we approach code in any language - how a change is made from the specification, functions before objects, purity and idempotency, types, structure and layering, errors without fallbacks, comments, dependencies, configuration and validation.
* [Python guidelines](guidelines/python.md) - How Python spells the coding guidelines for the api and the worker - toolchain and package layout, style, FastAPI, Pydantic, SQLAlchemy and Alembic, async, LangGraph and the AI gateway, and tests.
* [TypeScript guidelines](guidelines/typescript.md) - How TypeScript spells the coding guidelines for the web client - toolchain, types, the generated API client, React and server state, routing, styling, accessibility and tests.
* [Testing guidelines](guidelines/testing.md) - The test pyramid and which agent writes what, independence of acceptance tests from the implementation, determinism and fixtures, what makes a good assertion, and traceability from each test to its acceptance criterion.
* [Commits and pull requests](guidelines/commit-and-pr.md) - Commit format, branch naming, what a pull request must state, how specification changes travel, and the review order of the agent chain.

# Document conventions

* [Document conventions](guidelines/documents/common.md) - The layout, the eight rules, identifier families, traceability, frontmatter, addressing and the placement guide every document in this bundle obeys; read before writing or moving any document.
* [Document templates](guidelines/documents/templates.md) - The heading skeleton each of the eleven document types follows; read when creating a document or adding a concept heading to one.

# Requirements

* [Business requirements](requirements/business.md) - The product objective, the Sales and Admin roles, the RULE-nn business rules that bind every other document, the B-nn requirement register with priorities, the SC-x business scenarios and the assumptions the product depends on.
* [System requirements](requirements/system.md) - The S-XXX-nn functional obligations by area and the N-nn non-functional obligations, each with its priority, the business rows it realises, the flows and data entities it touches and the heading that specifies it.
* [Acceptance criteria](requirements/acceptance.md) - The AC-nn criteria in Given / When / Then form that QA turns into acceptance and end-to-end tests, the pass criteria of the four business scenarios and the release gate they are read against.
* [Traceability matrix](requirements/traceability.md) - Generated from the registers - every system and non-functional requirement with the business rows it realises, the flows and data entities it touches and the acceptance criteria that verify it.
* [Glossary](requirements/glossary.md) - Every domain term of LeadRadar with its meaning, the implementation identifier it maps to and the heading that defines it, and the values that are never translated.

# Architecture

* [Architecture overview](architecture/overview.md) - What LeadRadar is built from and why - principles, topology, runtime and fixture mode, store ownership, AI roles and their boundaries, degradation, the production path and the demo dataset with its seeded services and accounts.
* [SQL store](architecture/sql-store.md) - Every PostgreSQL table, column and enum of LeadRadar - identity, configuration, accounts, ingestion, signals and scores, feedback and evaluation, outreach and audit - with the scoring settings document, the audit vocabulary and the constraints.
* [Rules](architecture/rules.md) - The deterministic computations of LeadRadar - account identity, fetching, normalisation, triage, classification and escalation, evidence, the budget guard, Fit, Intent, decay, exclusion, Priority and bands, rescoring, alerts, discovery, feedback, evaluation, outreach grounding and retention - with worked scoring examples.
* [Interfaces](architecture/interfaces.md) - Every contract that crosses a boundary - the REST API the frontend calls, the in-process classifier, LLM, embedder, source plug-in and CRM ports - with every shape each carries and its source of truth.

# Decisions

* [Decisions](architecture/adrs/index.md) - Architecture decision records, one file per ADR

# Services

* [API service](architecture/services/api.md) - The FastAPI process - its responsibilities and boundary, the tables and rules it owns, request handling, transactions, enqueueing, the interactive AI calls it makes, and its configuration keys.
* [Worker service](architecture/services/worker.md) - The background process - job queue and priorities, run lifecycle and stages, the LangGraph signal graph, the AI gateway with its Jev and Anthropic adapters, the source plug-in adapters, the scheduler and housekeeping, and every pipeline configuration key.
* [Frontend](architecture/services/frontend.md) - The React web client - stack, routes and roles, navigation and page anatomy, visual language, score presentation, screen states, messages and dialogs, motion, screen labels, formatting, polling, tables and accessibility - with the shell-level FR rows every screen obeys and its configuration keys.

# Features

* [Service configuration](features/service-configuration.md) - How an Admin defines a service, its signal questions and its versioned scoring settings - ICP criteria, weights, half-lives, disqualifiers and thresholds - tries a question before saving it, previews a scoring change and activates it without code.
* [Accounts and discovery](features/accounts-and-discovery.md) - How Sales builds the target account list - CSV import with a dry run, manual entry, profile attributes, aliases, source addresses and minimal contacts - and how discovery suggests new accounts for a service that a person accepts or rejects.
* [Signal pipeline](features/signal-pipeline.md) - How an account refresh turns public sources into findings and scores - fetch, normalise, triage, classify with the fast classifier, escalate the uncertain, quote the evidence, score - on demand, on schedule, after a question change and after a scoring change, with the Runs and Source plug-ins screens.
* [Prospect dashboard](features/prospect-dashboard.md) - How Sales works the ranked prospects of a service, opens an account's why view with every point of its score traced to criteria and quoted signals, drills into evidence and score history, how an Admin adds an exception to a disqualifier, and how alerts surface accounts that need attention.
* [Evaluation and feedback](features/evaluation-and-feedback.md) - How feedback on leads and signals corrects scores and becomes labelled data, how the team labels passages blind, and how an Admin runs a quality check that measures precision, recall, escalation and calibration against the release gate.
* [Outreach and CRM](features/outreach-and-crm.md) - How Sales drafts an email or LinkedIn InMail grounded in an account's quoted signals and the service's value proposition, edits and exports it without the product ever sending it, and pushes an account's score and top signals to HubSpot.
* [Identity and access](features/identity-and-access.md) - How users sign in and out with local accounts, how sessions and lockout work, how the Sales and Admin roles are enforced, and how an Admin manages users.
* [Audit trail](features/audit-trail.md) - The append-only record of who changed what and of every classifier and LLM call with its model, prompt version, cost and outcome, as the Admin's Audit log screen filters and reads it back.
