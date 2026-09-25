# LeadRadar | AI-Powered B2B Sales Signals Platform

## Problem statement

Orange Systems sells advanced IT and digital transformation services across international markets. The sales team needs to identify the right companies, in the right market, at the right moment, with the right value proposition.

Today, this process is mostly manual. The sales team spends significant time researching companies, reading news, checking job postings, reviewing websites, scanning LinkedIn activity, and trying to understand whether a company may currently need services such as Agentic Process Automation, Cybersecurity services, or other IT services.

The key challenge is to **convert public information into clear, actionable sales signals**.

Orange Systems needs a flexible AI-powered platform where the sales team can define their own business questions, monitor public sources, detect relevant buying signals, score companies, and prioritize outreach based on evidence.

## Challenge brief

### AI B2B Platform

Build an AI-powered B2B sales intelligence platform that helps Orange Systems identify and prioritize potential clients based on public business signals.

The platform should allow users to configure service-specific signal questions, for example:

- Does the company mention process optimization, cost reduction, operational efficiency, or automation initiatives?
- Is the company hiring RPA developers, business analysts, automation engineers, AI specialists, or process excellence roles?

Based on answers to these questions, the platform should identify potential leads, explain why they are relevant, and assign a score.

**Target beneficiaries:** sales development teams at IT service providers.

## Solution scope

### Configuration

The platform should allow Orange Systems users to configure:

- Ideal Customer Profile criteria by market, industry, company size, geography
- Custom signal questions for each service
- Signal weights, for example high, medium, or low importance
- Negative signals or disqualification rules
- Scoring logic for lead prioritization

### Data ingestion

- **Crunchbase** — for company profiles, key people and corporate events
- **Company websites, newsrooms, annual reports and strategy publications** — for transformation, efficiency, AI and automation signals
- **Google News / NewsAPI / GDELT** — for recent company-related news and announcements
- **Corporate career pages and public job boards** — for hiring signals related to AI, RPA, process mining, process excellence, digital transformation, etc.
- **LinkedIn / Sales Navigator** *(optional)* — for manual validation, decision-makers, management changes, and public posts. The solution **must not depend** on LinkedIn scraping or API access.

### AI processing & scoring

- Large-scale data extraction and normalization from heterogeneous web sources
- Dynamic prospect scoring model — prioritize by readiness and likelihood to buy
- Signal detection: recent incidents, leadership changes, tech stack signals, compliance events

### Outreach generation module *(optional)*

- Personalized message generation based on collected company intelligence
- Customized value propositions mapped to specific company situation and context
- Multi-channel outreach drafts (email, LinkedIn InMail, etc.)

## Technical stack (expected)

### Data layer

- **Web scraping/crawling:** Playwright, Scrapy, or SerpAPI
- **Company, news & job data:** Crunchbase, NewsAPI, GDELT, RSSHub feeds, public career pages
- **Storage:** PostgreSQL or MongoDB for structured/unstructured signals

### AI / ML layer

- **LLMs** for signal extraction and message generation; any platform is allowed, cloud-based or self-hosted (OpenAI, Anthropic, or Llama)
- **LLM frameworks** like LangChain and LangGraph
- **Scoring pipeline:** ML classifier or rule-based scoring with explainability

### Frontend / API

- **Dashboard:** React
- **CRM integration hooks** *(optional)*: HubSpot

## Reference material

See [Annex 1: Participant Reference Pack](annex-1-participant-reference-pack.md) for the current manual sales process and two illustrative examples.

## Prizes

| Award | Prize | Teams |
|---|---|---|
| Winning team | €30,000 cash | Up to 1 team |

## Judging criteria

| Criterion | Weight | Description |
|---|---:|---|
| Signal Relevance & Accuracy | 25% | Quality and precision of identified prospect signals; low false-positive rate in prospect identification. |
| AI/ML Innovation | 20% | Sophistication of scoring model, creative use of LLMs, and originality of the overall AI approach. |
| Configurability | 20% | Ability to define custom signal questions, service categories, scoring rules, and ICP criteria. |
| Usability & UX | 15% | Clarity of the prospect dashboard; ease of use for non-technical sales teams without AI expertise. |
| Business Impact & Scalability | 10% | Potential ROI for Orange Systems; ability to scale to new markets, industries, and verticals. |
| Technical Execution | 10% | Robustness of data pipeline, API integrations, system reliability, and real-time processing capability. |
