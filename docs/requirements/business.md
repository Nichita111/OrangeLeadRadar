---
type: Requirements
title: Business requirements
description: The product objective, the Sales and Admin roles, the RULE-nn business rules that bind every other document, the B-nn requirement register with priorities, the SC-x business scenarios and the assumptions the product depends on.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# Business requirements and rules

## Objective

LeadRadar helps Orange Systems find the right companies, in the right market, at the right moment, with the right value proposition. The external brief is the [challenge brief](/reference/challenge-brief.md) and the manual process it replaces is in [Annex 1](/reference/annex-1-participant-reference-pack.md). For each Orange Systems service the product must:

1. let the team state, without code, which companies fit (the ICP), which public signals reveal a need, how strongly each counts, and what rules a company out;
2. gather recent public information about each target account from open sources, and from paid ones when available, without depending on LinkedIn;
3. answer every signal question against that information and keep each positive answer with a verbatim quote, its source and its date;
4. score and rank the accounts with an explanation a sales manager can read, check and challenge;
5. learn where it is wrong from the team's feedback and measure its own precision;
6. help write a first message grounded in the evidence, and hand the lead to the CRM.

## Roles

Two roles exist. These definitions are the source for every screen's access and for server-side authorisation.

**Sales** — a sales manager or sales development representative. May manage accounts and contacts, run refreshes and discovery, work prospects, read every explanation and the evidence, give feedback, label passages, draft outreach and push to the CRM. May not change services, questions or scoring, manage source plug-ins or users, add exceptions to disqualifiers, run quality checks or read the audit.

**Admin** — the owner of the sales-intelligence configuration. May do everything Sales may and, in addition, configure services, signal questions and scoring, manage source plug-ins and users, add and revoke exceptions, run quality checks and read the audit.

## Business rules

These rules bind every document. A requirement that would break one is invalid.

| Rule | Statement | Specified by |
|---|---|---|
| `RULE-01` | Only public sources are used, plus licensed Crunchbase data when available; LinkedIn is never read automatically, and a LinkedIn address is kept only for a person to open. | [Fetch window](/architecture/rules.md#fetch-window); [ADR-07](/architecture/adrs/adr-07-source-plug-ins-with-a-free-core.md) |
| `RULE-02` | No evidence, no finding: every finding carries a verbatim quote from a stored document with its address and date. | [Evidence extraction](/architecture/rules.md#evidence-extraction); principle P-02 of the [overview](/architecture/overview.md#principles) |
| `RULE-03` | Models answer questions and write text; deterministic rules alone compute every score, band, standing and exclusion. | [ADR-03](/architecture/adrs/adr-03-models-answer-rules-score.md); [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries) |
| `RULE-04` | Business configuration is data: services, questions, ICP, weights, disqualifiers and thresholds change without a code change or a restart. | [SQL store](/architecture/sql-store.md#configuration); [ADR-06](/architecture/adrs/adr-06-rule-based-scoring-with-versioned-settings.md) |
| `RULE-05` | Every score is reproducible from its scoring version, the in-force findings, feedback and exceptions, the account's attributes and its as-of time. | [Rescoring](/architecture/rules.md#rescoring); [Score breakdown](/architecture/rules.md#score-breakdown) |
| `RULE-06` | The product never contacts a prospect: outreach exists only as drafts a person copies or exports. | [Outreach grounding](/architecture/rules.md#outreach-grounding) |
| `RULE-07` | Contact data is minimal: name, job title, company and public source address; no email address or phone number is stored; a contact is erased on request and at the end of its retention. | [`contact`](/architecture/sql-store.md#contact); [ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md) |
| `RULE-08` | Paid sources are optional: every P0 capability works with the free core alone. | [Plug-in availability](/architecture/rules.md#plug-in-availability); [ADR-07](/architecture/adrs/adr-07-source-plug-ins-with-a-free-core.md) |
| `RULE-09` | Every configuration change, exception, piece of feedback, run and classifier or LLM call is audited. | [Audit actions](/architecture/sql-store.md#audit-actions) |
| `RULE-10` | An excluded account or a customer is never ranked, but stays visible with its reason. | [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) |

## Business requirements

Each requirement states one business obligation and carries a priority. `P0` is in the release gate; `P1` is required for a credible product but outside the gate; `P2` is deferred. The `S-` and `AC-` rows that realise or verify a row inherit its priority, and are found by grepping its identifier.

### Configure services

| ID | Requirement | Priority |
|---|---|---|
| `B-01` | An Admin shall define the services accounts are scored for, each with a description and a value proposition, without code. | P0 |
| `B-02` | An Admin shall define each service's ideal customer profile by industry, company size, revenue, geography and operational complexity, with a weight per criterion. | P0 |
| `B-03` | An Admin shall define each service's signal questions, each with an answer type, a positive or negative direction and the kinds of source it applies to. | P0 |
| `B-04` | An Admin shall set each question's weight and half-life, the rules that exclude an account, and the Fit, Intent and band settings, and apply them together as one versioned change. | P0 |
| `B-05` | A scoring change shall re-rank accounts without collecting data again, and a new or changed question shall re-check stored data for that question only. | P0 |
| `B-06` | An Admin shall try a question on sample text or an account, and see the effect of a scoring change on the ranking, before applying it. | P1 |

### Manage accounts

| ID | Requirement | Priority |
|---|---|---|
| `B-07` | Sales shall import target accounts from a CSV file with a preview of what will change, and add accounts one by one. | P0 |
| `B-08` | Sales shall keep each account's profile, alternative names and publication addresses, with values entered by a person taking precedence over collected ones. | P0 |
| `B-09` | Sales shall record decision-makers with the minimum personal data. | P1 |
| `B-10` | The product shall suggest new accounts that fit a service, and Sales shall accept or reject each suggestion. | P1 |
| `B-37` | The product shall fill in an account's missing profile details from data providers and by classification. | P1 |

### Detect signals

| ID | Requirement | Priority |
|---|---|---|
| `B-11` | The product shall gather recent public information about each account from the enabled sources, working with the free sources alone. | P0 |
| `B-12` | The product shall answer every active signal question against the gathered information and keep each positive answer as a finding with its verbatim evidence. | P0 |
| `B-13` | The product shall read sources in any language and show evidence in the original with an English translation, in an English interface. | P0 |
| `B-14` | Sales shall refresh an account on demand and follow the progress live. | P0 |
| `B-15` | Every account shall be refreshed on a schedule. | P1 |
| `B-36` | The product shall find an account's newsroom, investor-relations, careers and feed addresses by itself. | P1 |

### Score and prioritise

| ID | Requirement | Priority |
|---|---|---|
| `B-16` | Each account shall have, per service, a Fit score, an Intent score and a Priority score with a Hot, Warm or Cold band. | P0 |
| `B-17` | Every score shall be explained so that each point traces to an ICP criterion or a quoted finding. | P0 |
| `B-18` | Negative signals shall lower Intent; disqualifiers shall exclude an account with the reason; an Admin shall be able to make an exception with a note. | P0 |
| `B-19` | Older evidence shall count less, by a half-life. | P0 |
| `B-20` | Sales shall see how an account's score changed over time and why. | P1 |

### Work the prospects

| ID | Requirement | Priority |
|---|---|---|
| `B-21` | Sales shall see each service's ranked prospects and filter them. | P0 |
| `B-22` | Sales shall open an account's explanation and follow each finding to its source. | P0 |
| `B-23` | Sales shall be alerted to strong new signals and to accounts whose band rose. | P1 |
| `B-24` | Sales shall mark leads and findings as right or wrong; a wrong finding shall stop counting and a customer shall leave the ranking. | P1 |

### Outreach and CRM

| ID | Requirement | Priority |
|---|---|---|
| `B-25` | Sales shall get an email or InMail draft grounded in the account's evidence and the service's value proposition, which the product never sends. | P1 |
| `B-26` | Sales shall push an account's score and top signals to HubSpot. | P2 |

### Quality

| ID | Requirement | Priority |
|---|---|---|
| `B-27` | The team shall label passages in the product and measure the precision of signal detection, and a release shall require the precision the release gate sets. | P0 |
| `B-28` | Finding feedback shall add to the labelled set. | P1 |
| `B-29` | Weights shall be learned from sales outcomes and proposed as a scoring draft. | P2 |

### Operate

| ID | Requirement | Priority |
|---|---|---|
| `B-30` | Users shall sign in with the Sales or Admin role, and each role shall be enforced. | P0 |
| `B-31` | Configuration changes, exceptions, feedback, runs and AI calls shall be recorded in an audit trail. | P0 |
| `B-32` | An Admin shall read and filter the audit trail. | P1 |
| `B-33` | AI spend and source usage shall be capped by configuration. | P0 |
| `B-34` | The product shall run with one command locally and on one cloud machine. | P0 |
| `B-35` | The demo shall run offline and repeatably from recorded data. | P0 |

## Scenarios

The scenarios are the business definition of done. Each `SC-` row passes by the acceptance criteria that name it in [scenario pass criteria](/requirements/acceptance.md#scenario-pass-criteria), walked through with the [demo dataset](/architecture/overview.md#demo-dataset).

**`SC-A` First ranking.** Sales imports the demo accounts, refreshes Lufthansa Group and DHL Group and watches the runs progress. Prospects for Intelligent Automation ranks both with a band. DHL Group's explanation shows its sector and region fit, its AI and automation signals with German quotes and English translations, and its in-house automation capability counting against it; one signal opens the original press release.

**`SC-B` Tuning without refetching.** An Admin raises the weight of automation hiring and activates the change with a note; the ranking changes without any document being fetched, and the history names the new version and its note. The Admin revises the cost-programme question; only that question is re-checked on stored passages.

**`SC-C` Negative signals and exclusions.** An account with a strong in-house automation capability scores lower Intent than it would without it. An account outside the target region is excluded with that reason, stays visible under Excluded, returns to the ranking when an Admin adds an exception, and is excluded again when it is revoked.

**`SC-D` Quality gate.** The team labels at least `EVAL_MIN_ITEMS` passages; an Admin runs a quality check with the configured classifier, which reports precision at or above `EVAL_MIN_PRECISION` and shows how often the LLM was needed.

## Assumptions and constraints

| Item | Statement |
|---|---|
| Scope | The specification describes an MVP buildable during the hackathon plus a written [production path](/architecture/overview.md#production-path). P0 is the demo path end to end: configure a service, import accounts, refresh on demand, get findings with evidence, see the ranking and the explanation, and pass the quality gate. Scheduled refresh, automatic source detection, profile enrichment and the moderated usability walkthrough are P1. The hackathon date and team size are not known; if they cut scope further, P1 rows go first. |
| Reference material | The files in `docs/reference/` are the external brief as received; requirements cite them and they are never edited to match the specification. |
| ICP attributes | ICP criteria are industry, employee range, revenue range, countries and operational complexity; complexity is a classified level when no one entered it. |
| Question shape | Questions are yes/no, scale or choice, matching the classifier's question types; weight levels are High, Medium, Low and None. |
| Priority | Priority is a weighted sum of Fit and Intent, shown only when Fit reaches a minimum; all its numbers are scoring settings. |
| Suggested accounts | A suggested account is never refreshed or scored until a person accepts it. |
| Account identity | An account's website domain is its identity; news is matched to accounts by the classifier. |
| Shared accounts | Accounts are shared by the whole team; there is no per-user ownership in the MVP. |
| Alerts | Alerts appear in the product only, with no email or chat delivery. |
| Stored documents | For each fetched document the product stores its extracted text, address and dates for a retention period, and shows the text only as evidence. |
| Crawling | The crawler obeys `robots.txt`, identifies itself and respects per-source limits; nothing reads LinkedIn automatically. |
| Jev | Jev is served by OpenRouter as `typesafe/jev-1.13` and billed to the same OpenRouter key ([ADR-15](/architecture/adrs/adr-15-openrouter-as-the-llm-provider.md)). The LLM classifier is the default until a quality check shows Jev passes the gate. |
| Data providers | Keys for Crunchbase, NewsAPI and SerpAPI are being requested; each is optional. |
| LLM provider | An OpenRouter account with API access is available; the model of each AI role is chosen by configuration, and each call's price is the cost OpenRouter reports ([ADR-15](/architecture/adrs/adr-15-openrouter-as-the-llm-provider.md)). |
| Hosting | The demo runs on one cloud machine in an EU region. |
| Language | The interface is English only; sources may be in any language. |
