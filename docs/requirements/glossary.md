---
type: Glossary
title: Glossary
description: Every domain term of LeadRadar with its meaning, the implementation identifier it maps to and the heading that defines it, and the values that are never translated.
status: draft
tags: [accounts-and-discovery, audit-trail, evaluation-and-feedback, identity-and-access, outreach-and-crm, prospect-dashboard, service-configuration, signal-pipeline]
---

# Glossary

## Terms

A term is the one name of its concept in prose. **Identifier** is the name code, tables and API paths use; where it differs from the term, the pair is fixed here and nowhere else. The word a screen shows for a term is its [screen label](/architecture/services/frontend.md#screen-labels), a presentation of the term and never a second name.

| Term | Meaning | Identifier | Defined in |
|---|---|---|---|
| Account | A company that may buy, identified by its registrable web domain and shared by the team. | `account` | [`account`](/architecture/sql-store.md#account) |
| Account alias | Another name an account is reported under. | `account_alias` | [`account_alias`](/architecture/sql-store.md#account_alias) |
| Account refresh | A run that fetches, processes, triages, classifies and scores one account. | `ACCOUNT_REFRESH` | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| Account source | An address where an account publishes: website, newsroom, investor relations, careers or feed. | `account_source` | [`account_source`](/architecture/sql-store.md#account_source) |
| Admin | The role that configures services, scoring, plug-ins and users on top of everything Sales does. | `ADMIN` | [Roles](/requirements/business.md#roles) |
| AI call | One request to the classifier or the LLM, audited with its role, model and cost. | `AI_CALL` | [Audit actions](/architecture/sql-store.md#audit-actions) |
| AI role | The purpose an AI call serves: classifier, escalation, evidence, discovery extraction or outreach. | `ai_role` | [AI roles and boundaries](/architecture/overview.md#ai-roles-and-boundaries) |
| Alert | A notice that an account produced a strong new signal or rose in band. | `alert` | [Alerts](/architecture/rules.md#alerts) |
| Answer type | How a signal question is answered: yes/no, scale or choice. | `answer_type` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| Audit event | One append-only record of an action. | `audit_event` | [`audit_event`](/architecture/sql-store.md#audit_event) |
| Band | Hot, Warm or Cold, from a ranked account's Priority. | `band` | [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) |
| Budget guard | The rule that stops LLM calls — OpenRouter chat completions — once the day's spend reaches its cap; Jev calls are not capped. | — | [Budget guard](/architecture/rules.md#budget-guard) |
| Calibration | How closely classifier confidence matches the observed share of positives. | `calibration` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Classification | The classifier's answer to one question on one passage at one question revision. | `classification` | [`classification`](/architecture/sql-store.md#classification) |
| Classifier | The fast model that returns probabilities over fixed answers: Jev, or the LLM classifier adapter. | `CLASSIFIER` | [Classifier](/architecture/interfaces.md#classifier) |
| Confidence | How sure the deciding model was of a finding, from 0 to 1. | `confidence` | [`finding`](/architecture/sql-store.md#finding) |
| Contact | A decision-maker at an account, kept to the minimum. | `contact` | [`contact`](/architecture/sql-store.md#contact) |
| Discovery | A run that proposes companies not yet accounts for a service. | `DISCOVERY` | [Discovery](/architecture/rules.md#discovery) |
| Discovery candidate | A company proposed by discovery that a person accepts or rejects. | `discovery_candidate` | [`discovery_candidate`](/architecture/sql-store.md#discovery_candidate) |
| Disqualifier | A rule of the scoring settings that excludes an account from the ranking. | `disqualifiers` | [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |
| Disqualifier override | An Admin's exception that one disqualifier does not apply to one account. | `disqualifier_override` | [`disqualifier_override`](/architecture/sql-store.md#disqualifier_override) |
| Document | One fetched item: article, page, report, posting or profile. | `document` | [`document`](/architecture/sql-store.md#document) |
| Escalation | Sending an uncertain classifier answer to the LLM for a final verdict. | `escalated` | [Escalation](/architecture/rules.md#escalation) |
| Escalation band | The range of `p_positive` between `ESCALATION_LOWER` and `ESCALATION_UPPER` that is escalated. | — | [Escalation](/architecture/rules.md#escalation) |
| Escalation rate | The share of evaluated pairs that were escalated. | `escalation_rate` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Evaluation item | A labelled pair: the strength a person says a passage shows for a question. | `evaluation_item` | [`evaluation_item`](/architecture/sql-store.md#evaluation_item) |
| Evaluation run | A quality check replaying the classification cascade over the labels. | `EVALUATION` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Evidence quote | The verbatim sentence of a passage that a finding rests on. | `quote` | [Evidence extraction](/architecture/rules.md#evidence-extraction) |
| Finding | A positive answer to a signal question for an account, with its evidence quote. | `finding` | [`finding`](/architecture/sql-store.md#finding) |
| Finding feedback | A user's verdict that a finding is correct or wrong. | `finding_feedback` | [`finding_feedback`](/architecture/sql-store.md#finding_feedback) |
| Fit score | 0–100: how well an account matches a service's ICP. | `fit` | [Fit score](/architecture/rules.md#fit-score) |
| Free core | The source plug-ins that need no key: GDELT, RSS, website and careers. | — | [`source_plugin`](/architecture/sql-store.md#source_plugin) |
| Half-life | The age at which a finding counts half as much. | `half_life_days` | [Recency decay](/architecture/rules.md#recency-decay) |
| ICP | Ideal customer profile: the companies a service is for. | `icp_criteria` | [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |
| ICP criterion | One weighted condition of the ICP: industry, geography, size, revenue or complexity. | `icp_criteria[]` | [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |
| Impact report | What the product saved over a recent period: accounts researched, manual hours replaced, cost and time per refresh, proven precision. | `impact` | [Impact](/architecture/rules.md#impact) |
| In force | Counting now: an `ACTIVE` finding, the latest feedback row, an `ACTIVE` exception. | — | [`finding`](/architecture/sql-store.md#finding) |
| Industry | An Admin-maintained sector an account belongs to and an ICP criterion names. | `industry` | [`industry`](/architecture/sql-store.md#industry) |
| Intent score | 0–100: how strongly an account's recent findings show a need for a service. | `intent` | [Intent score](/architecture/rules.md#intent-score) |
| Jev | TypeSafe AI's classification model, served through OpenRouter; one of the two classifier adapters. | `JEV` | [AI gateway](/architecture/services/worker.md#ai-gateway) |
| Label queue | The stratified list of pairs offered for labelling. | — | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Lead feedback | A user's verdict on a lead: relevant, not relevant or already a customer. | `lead_feedback` | [`lead_feedback`](/architecture/sql-store.md#lead_feedback) |
| LeadRadar | This product. | — | [Architecture overview](/architecture/overview.md#purpose) |
| Market | An Admin-maintained, named group of countries, chosen in ICP geography criteria as a shortcut for its countries. | `market` | [`market`](/architecture/sql-store.md#market) |
| Missed evidence | The share of labelled passages the selection leaves unread that hold a signal. | `missed_evidence` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Negative signal | A finding of a negative question, which lowers Intent. | `NEGATIVE` | [Intent score](/architecture/rules.md#intent-score) |
| Outreach draft | A message a person may send, drafted from findings; never sent by the product. | `outreach_draft` | [`outreach_draft`](/architecture/sql-store.md#outreach_draft) |
| Passage | A piece of a document: what the classifier reads and a finding quotes. | `chunk` | [`chunk`](/architecture/sql-store.md#chunk) |
| Passage header | The line naming account, document, section and date that a passage is read with; never quoted. | — | [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection) |
| Persona | The role category of a contact, such as CIO or head of automation. | `persona` | [`contact`](/architecture/sql-store.md#contact) |
| Polarity | Whether a question's findings raise or lower Intent. | `polarity` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| Precision | The share of predicted positives that the labels confirm. | `precision` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Priority score | 0–100: the weighted combination of Fit and Intent that ranks accounts. | `priority` | [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) |
| Prospect | An account in a service's ranking. | `prospects` | [Prospects](/features/prospect-dashboard.md#prospects) |
| Question revision | The version of a signal question's content; a new revision reclassifies. | `revision` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| Question-scoped retrieval | Ranking a long document's passages for one question by keyword and by meaning, fused by rank. | — | [Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection) |
| Recall | The share of labelled positives that were predicted positive. | `recall` | [Evaluation metrics](/architecture/rules.md#evaluation-metrics) |
| Recency decay | The halving of a finding's weight with every half-life of age. | `decay` | [Recency decay](/architecture/rules.md#recency-decay) |
| Release gate | The criteria and scenarios a release must pass, including the precision threshold. | — | [Release gate](/requirements/acceptance.md#release-gate) |
| Rescore | Recomputing scores from stored findings without fetching or classifying. | `RESCORE` | [Rescoring](/architecture/rules.md#rescoring) |
| Run | A unit of background work a user can follow. | `pipeline_run` | [`pipeline_run`](/architecture/sql-store.md#pipeline_run) |
| Sales | The role that works accounts, prospects, feedback, labels and outreach. | `SALES` | [Roles](/requirements/business.md#roles) |
| Score breakdown | The stored attribution of every point of a score to a criterion or a finding. | `breakdown` | [Score breakdown](/architecture/rules.md#score-breakdown) |
| Scoring settings | The configuration a service is scored with: ICP, weights, half-lives, disqualifiers, thresholds. | `settings` | [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |
| Scoring version | One immutable, numbered version of a service's scoring settings. | `scoring_config` | [`scoring_config`](/architecture/sql-store.md#scoring_config) |
| Section path | The headings, or the page, above a passage in its document. | `section` | [`chunk`](/architecture/sql-store.md#chunk) |
| Service | An Orange Systems service that accounts are scored for. | `service` | [`service`](/architecture/sql-store.md#service) |
| Session | A signed-in browser session. | `auth_session` | [`auth_session`](/architecture/sql-store.md#auth_session) |
| Signal question | A configurable question a passage can answer, revealing a need for a service. | `signal_question` | [`signal_question`](/architecture/sql-store.md#signal_question) |
| Source plug-in | An adapter that fetches from one kind of source. | `source_plugin` | [`source_plugin`](/architecture/sql-store.md#source_plugin) |
| Source type | The kind of document: news, company publication, job posting or company profile. | `source_type` | [`document`](/architecture/sql-store.md#document) |
| Standing | Whether an account is ranked, below fit, disqualified or a customer, for a service. | `standing` | [Priority, standing and band](/architecture/rules.md#priority-standing-and-band) |
| Strength | How strongly a passage answers a question: none, weak, medium or strong. | `strength` | [`finding`](/architecture/sql-store.md#finding) |
| Triage | Deciding whether a document is about its account and relevant to which services. | `document_triage` | [Triage](/architecture/rules.md#triage) |
| Value proposition | What a service offers a prospect, used in outreach. | `value_proposition` | [`service`](/architecture/sql-store.md#service) |
| Weight level | High, Medium, Low or None: how much an ICP criterion or question counts. | `weight` | [scoring settings document](/architecture/sql-store.md#scoring-settings-document) |

## Do not translate

Evidence quotes are shown as written, with their translation beside them, never instead of them. Translations and screens keep these unchanged: the product name LeadRadar; Jev; company, product and person names inside quotes; service codes and question keys; enum values; configuration keys; identifiers of the `API-`, `AC-`, `FL-`, `FR-` and `WF-` families.

## Retired identifiers

| Identifier | Reason | Replaced by |
|---|---|---|
| `B-38` | Jev became available through OpenRouter, so keeping it classifying under an exhausted budget no longer needed its own should-have row | `B-33` through `S-SIG-08` |
| `S-SIG-10` | The same obligation belongs to the budget guard, as first specified | `S-SIG-08` |
