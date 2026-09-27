"""Demo signals and contacts for `leadradar-seed-demo`: gives a spread of demo accounts their own
documents, passages, classifications and findings for both seeded services, and one or two
contacts each, then scores them through the SCORE step, so Prospects ranks them apart and the
Outreach composer has grounded findings and a contact to draft for. It never fetches and never
calls a classifier or an LLM; the rows are those the signal pipeline would have written.

Every document lives under `DEMO_SIGNAL_HOST`, so the seeded evidence is never mistaken for a
fetched page. A document or contact already there is skipped, so running the seed again adds only
what joined the dataset since, and a user's later changes stay.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    AccountStatus,
    ClassificationStatus,
    ContactPersona,
    ContactPersonaOrigin,
    DocumentSourceType,
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.db.models.accounts import Account, Contact
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps.score import run_score_step

DEMO_SIGNAL_HOST = "https://demo-signals.leadradar.local"

_IA = "INTELLIGENT_AUTOMATION"
_CYBER = "CYBERSECURITY"
_SD = "SOFTWARE_DEVELOPMENT"
_QA = "QUALITY_ASSURANCE"

_S = FindingStrength.STRONG
_M = FindingStrength.MEDIUM
_W = FindingStrength.WEAK

_NEWS = DocumentSourceType.NEWS
_PUBLICATION = DocumentSourceType.COMPANY_PUBLICATION
_JOBS = DocumentSourceType.JOB_POSTING
_PROFILE = DocumentSourceType.COMPANY_PROFILE

_PLUGIN_BY_SOURCE_TYPE = {
    _NEWS: SourcePluginCode.GDELT,
    _PUBLICATION: SourcePluginCode.WEBSITE,
    _JOBS: SourcePluginCode.CAREERS,
    _PROFILE: SourcePluginCode.WEBSITE,
}


@dataclass(frozen=True)
class _SignalSpec:
    """One seeded document with the one finding it carries. `text` holds `quote` verbatim, as a
    finding's quote is always a span of its passage."""

    service_code: str
    question_key: str
    strength: FindingStrength
    confidence: float
    source_type: DocumentSourceType
    days_ago: int
    title: str
    lead: str
    quote: str
    tail: str
    rationale: str
    language: str = "en"
    quote_en: str | None = None
    option_key: str | None = None

    @property
    def text(self) -> str:
        return f"{self.lead} {self.quote} {self.tail}"


@dataclass(frozen=True)
class _ContactSpec:
    full_name: str
    job_title: str
    persona: ContactPersona


# Account domain → its signals. Accounts left out keep no seeded signal, so Prospects shows a
# spread from strong intent to none.
_DEMO_SIGNALS: dict[str, tuple[_SignalSpec, ...]] = {
    "lufthansagroup.com": (
        _SignalSpec(
            _IA,
            "COST_PROGRAM",
            _S,
            0.93,
            _NEWS,
            12,
            "Lufthansa Group widens its turnaround programme",
            "The airline group presented its half-year figures on Thursday.",
            "Lufthansa Group expands its turnaround programme with a target of EUR 2.5 billion "
            "in annual savings by 2028, with administrative processes named as a main lever.",
            "Management said the savings would come from ground operations, finance and "
            "customer service.",
            "Names a group-wide savings target with administrative processes as a lever.",
        ),
        _SignalSpec(
            _IA,
            "SHARED_SERVICES",
            _M,
            0.84,
            _PUBLICATION,
            40,
            "Consolidating finance services across the group airlines",
            "Group Finance published its operating model update for the airlines.",
            "Accounting for Lufthansa, SWISS, Austrian and Brussels Airlines will move into a "
            "single global business services unit in Krakow and Frankfurt over the next two "
            "years.",
            "The unit will standardise invoice handling and period-end closing.",
            "Consolidates finance processes of several airlines into one shared service unit.",
        ),
        _SignalSpec(
            _IA,
            "AUTOMATION_HIRING",
            _M,
            0.81,
            _JOBS,
            6,
            "Senior Process Automation Engineer (m/f/d)",
            "Lufthansa Group Business Services is growing its automation team in Frankfurt.",
            "You will design and build RPA and AI-agent workflows for accounts payable, travel "
            "expenses and crew scheduling, working with process owners across the group.",
            "Experience with UiPath or Power Automate is an advantage.",
            "Hires an automation engineer for finance and operations processes.",
        ),
        _SignalSpec(
            _CYBER,
            "REGULATION_PRESSURE",
            _M,
            0.8,
            _PUBLICATION,
            55,
            "Annual report 2025: risk and opportunity report",
            "Aviation is classed as critical infrastructure in the EU.",
            "The Group is preparing its IT and operational technology for the requirements of "
            "NIS2, which apply to its airlines and maintenance companies from 2026.",
            "A group-wide programme reports to the Executive Board.",
            "States that NIS2 applies to the group and a programme is under way.",
        ),
    ),
    "dhl.com": (
        _SignalSpec(
            _IA,
            "AUTOMATION_INITIATIVE",
            _S,
            0.94,
            _NEWS,
            9,
            "DHL Group scales AI agents in customer service",
            "DHL Group spoke about its Strategy 2030 at an investor event.",
            "DHL Group plans to roll out AI agents for shipment tracking enquiries and customs "
            "document checks in 40 countries, after a pilot that handled a third of all "
            "enquiries without human intervention.",
            "The company expects the rollout to be completed within 18 months.",
            "Describes a large rollout of AI agents in customer and customs processes.",
        ),
        _SignalSpec(
            _IA,
            "NEW_EXECUTIVE",
            _M,
            0.86,
            _NEWS,
            30,
            "New Chief Process Officer at DHL eCommerce",
            "DHL eCommerce announced changes to its management board.",
            "Dr. Katrin Maurer has been appointed Chief Process Officer of DHL eCommerce and "
            "will lead process excellence and automation across its European parcel networks.",
            "She joins from a global consumer goods company.",
            "Appoints a new executive responsible for process excellence and automation.",
        ),
        _SignalSpec(
            _CYBER,
            "SECURITY_INCIDENT",
            _W,
            0.72,
            _NEWS,
            70,
            "Phishing wave targets parcel customers",
            "Consumer protection groups warned of fake delivery notifications.",
            "A phishing campaign impersonating DHL parcel notifications affected customers in "
            "several countries, and the company said it was strengthening its email "
            "authentication.",
            "No DHL systems were compromised, a spokesperson said.",
            "Reports a phishing campaign using the brand; weak because no breach occurred.",
        ),
    ),
    "kuehne-nagel.com": (
        _SignalSpec(
            _IA,
            "DIGITAL_TRANSFORMATION",
            _M,
            0.83,
            _PUBLICATION,
            20,
            "Roadmap 2026: a digital backbone for every shipment",
            "Kuehne+Nagel updated its Roadmap 2026 in its annual report.",
            "Kuehne+Nagel is replacing its freight forwarding systems with one global platform "
            "and redesigning order-to-cash processes around it.",
            "The migration will run country by country until 2027.",
            "Describes a platform change that redesigns core processes.",
        ),
        _SignalSpec(
            _IA,
            "COST_PROGRAM",
            _M,
            0.79,
            _NEWS,
            45,
            "Kuehne+Nagel announces efficiency measures",
            "The logistics company reported lower sea freight volumes.",
            "Kuehne+Nagel launched an efficiency programme targeting CHF 200 million in cost "
            "reductions, mainly in overhead and back-office functions.",
            "Analysts welcomed the measures.",
            "Announces a cost-reduction programme in back-office functions.",
        ),
    ),
    "siemens.com": (
        _SignalSpec(
            _IA,
            "IN_HOUSE_AUTOMATION",
            _S,
            0.9,
            _PUBLICATION,
            25,
            "Inside the Siemens Automation Center of Excellence",
            "Siemens has built its own automation capability over eight years.",
            "The Siemens Automation Center of Excellence runs more than 3,000 bots and its own "
            "AI-agent platform, built and operated entirely in-house.",
            "It serves all business units worldwide.",
            "Describes a strong in-house automation centre of excellence.",
        ),
        _SignalSpec(
            _IA,
            "AUTOMATION_INITIATIVE",
            _M,
            0.77,
            _NEWS,
            18,
            "Siemens pushes generative AI into its operations",
            "Siemens spoke about its One Tech Company programme.",
            "Siemens wants to use generative AI in procurement and order management across all "
            "its factories by the end of next year.",
            "The programme is led by its own digital unit.",
            "Plans AI projects in procurement and order management.",
        ),
    ),
    "bosch.com": (
        _SignalSpec(
            _IA,
            "COST_PROGRAM",
            _S,
            0.92,
            _NEWS,
            14,
            "Bosch steps up savings in its mobility business",
            "Bosch confirmed further measures for its Mobility business sector.",
            "Bosch aims to cut annual costs in its Mobility business by EUR 2.5 billion by "
            "2030, including a leaner administration and simplified processes.",
            "Talks with employee representatives are ongoing.",
            "Names a savings target that includes simplifying administrative processes.",
        ),
        _SignalSpec(
            _IA,
            "AUTOMATION_HIRING",
            _M,
            0.8,
            _JOBS,
            4,
            "Process Mining Specialist (m/w/d)",
            "Bosch Global Business Services is looking for support in Stuttgart.",
            "Sie analysieren End-to-End-Prozesse mit Celonis und identifizieren "
            "Automatisierungspotenziale in Finanzen und Einkauf.",
            "Wir bieten flexible Arbeitszeiten.",
            "Hires a process mining specialist to find automation potential.",
            language="de",
            quote_en="You will analyse end-to-end processes with Celonis and identify automation "
            "potential in finance and procurement.",
        ),
        _SignalSpec(
            _CYBER,
            "SECURITY_HIRING",
            _M,
            0.78,
            _JOBS,
            10,
            "OT Security Engineer - Plant Security",
            "Bosch is building up security for its manufacturing plants.",
            "We are hiring OT security engineers to set up monitoring and incident response for "
            "more than 200 plants worldwide.",
            "You will report to the Chief Information Security Officer.",
            "Hires security engineers to build plant monitoring and response.",
        ),
    ),
    "zf.com": (
        _SignalSpec(
            _IA,
            "SHARED_SERVICES",
            _M,
            0.82,
            _NEWS,
            28,
            "ZF bundles administrative functions",
            "ZF Friedrichshafen continues its transformation.",
            "ZF will bundle finance, HR and purchasing administration of its divisions into "
            "regional shared service centres in Poland, Serbia and Portugal.",
            "The move affects several hundred roles in Germany.",
            "Consolidates administrative functions into shared service centres.",
        ),
        _SignalSpec(
            _CYBER,
            "NEW_CISO",
            _M,
            0.85,
            _NEWS,
            35,
            "ZF appoints new Chief Information Security Officer",
            "ZF announced a change in its IT leadership.",
            "Markus Feld has been appointed Chief Information Security Officer of ZF Group, "
            "reporting to the CIO.",
            "He previously led security at a European automotive supplier.",
            "Appoints a new CISO.",
        ),
    ),
    "ubs.com": (
        _SignalSpec(
            _IA,
            "COST_PROGRAM",
            _S,
            0.91,
            _NEWS,
            16,
            "UBS raises its gross cost savings target",
            "UBS reported quarterly results after the Credit Suisse integration.",
            "UBS raised its gross cost savings ambition to USD 13 billion by the end of 2026, "
            "with a large part coming from operations and technology.",
            "The bank said decommissioning legacy applications was a key driver.",
            "Raises a cost savings target driven by operations and technology.",
        ),
        _SignalSpec(
            _CYBER,
            "REGULATION_PRESSURE",
            _S,
            0.88,
            _PUBLICATION,
            22,
            "Operational resilience under DORA",
            "UBS describes its approach to operational resilience.",
            "As a significant institution, UBS must meet the Digital Operational Resilience Act "
            "for its EU entities, including threat-led penetration testing and third-party "
            "risk registers.",
            "Implementation is overseen by the Group Chief Operating Officer.",
            "States that DORA applies, with testing and third-party requirements.",
        ),
        _SignalSpec(
            _CYBER,
            "CLOUD_MIGRATION",
            _M,
            0.76,
            _NEWS,
            50,
            "UBS moves workloads to the cloud",
            "UBS continues to modernise its technology estate.",
            "UBS plans to move a majority of its applications to the public cloud as it "
            "decommissions the former Credit Suisse infrastructure.",
            "The bank works with two hyperscalers.",
            "Runs a large cloud migration programme.",
        ),
    ),
    "allianz.com": (
        _SignalSpec(
            _IA,
            "AUTOMATION_INITIATIVE",
            _M,
            0.8,
            _NEWS,
            21,
            "Allianz automates claims with AI",
            "Allianz presented its productivity agenda.",
            "Allianz wants to handle 60 percent of simple motor and property claims end to end "
            "with AI and automation by 2027.",
            "Human experts will focus on complex claims.",
            "Plans AI and automation in claims handling.",
        ),
        _SignalSpec(
            _CYBER,
            "SECURITY_INCIDENT",
            _M,
            0.82,
            _NEWS,
            60,
            "Customer data exposed at insurance subsidiary",
            "An insurance subsidiary in North America disclosed an incident.",
            "Hackers accessed a cloud-based CRM system of an Allianz subsidiary and obtained "
            "personal data of a majority of its customers.",
            "The company notified the authorities and affected customers.",
            "Reports a data breach at a subsidiary.",
        ),
    ),
    "munichre.com": (
        _SignalSpec(
            _CYBER,
            "MANAGED_SOC_IN_PLACE",
            _M,
            0.8,
            _PUBLICATION,
            40,
            "Our security operations",
            "Munich Re describes how it protects its systems.",
            "Munich Re's security operations centre is run together with a long-standing "
            "managed security service provider, around the clock.",
            "The partnership was extended last year.",
            "Names an existing managed SOC provider.",
        ),
        _SignalSpec(
            _IA,
            "DIGITAL_TRANSFORMATION",
            _W,
            0.68,
            _PUBLICATION,
            90,
            "Ambition 2025: technology as an enabler",
            "Munich Re looks back on its Ambition 2025 programme.",
            "Munich Re continues to digitise underwriting and reinsurance administration as "
            "part of its strategy.",
            "Details of the next programme will follow.",
            "Describes a general digitalisation effort without specifics.",
        ),
    ),
    "zurich.com": (
        _SignalSpec(
            _CYBER,
            "NEW_CISO",
            _S,
            0.87,
            _NEWS,
            11,
            "Zurich names new Group CISO",
            "Zurich Insurance Group announced changes to its technology leadership.",
            "Zurich Insurance Group has appointed Elena Brunner as Group Chief Information "
            "Security Officer, effective next month.",
            "She will focus on cyber resilience and regulatory readiness.",
            "Appoints a new group CISO.",
        ),
        _SignalSpec(
            _CYBER,
            "SECURITY_HIRING",
            _M,
            0.79,
            _JOBS,
            3,
            "SOC Analyst Level 2",
            "Zurich is expanding its Cyber Defence Center.",
            "We are looking for SOC analysts to join our 24/7 security monitoring team in "
            "Zurich and Barcelona.",
            "Knowledge of Microsoft Sentinel is a plus.",
            "Hires SOC analysts.",
        ),
        _SignalSpec(
            _IA,
            "NEW_EXECUTIVE",
            _W,
            0.7,
            _PROFILE,
            80,
            "Group Executive Committee",
            "Zurich lists its Group Executive Committee members.",
            "The Group Chief Operations Officer oversees technology, operations and the "
            "transformation office.",
            "The committee meets monthly.",
            "Names a transformation office under the COO; weak, no new appointment.",
        ),
    ),
    "erstegroup.com": (
        _SignalSpec(
            _CYBER,
            "REGULATION_PRESSURE",
            _M,
            0.81,
            _NEWS,
            26,
            "Erste Group prepares for DORA",
            "Austrian banks are preparing for new EU rules.",
            "Erste Group is investing in its ICT risk management and incident reporting to "
            "comply with DORA across its seven core markets.",
            "The bank set up a dedicated programme office.",
            "Invests to comply with DORA in its core markets.",
        ),
        _SignalSpec(
            _IA,
            "AUTOMATION_INITIATIVE",
            _M,
            0.78,
            _NEWS,
            33,
            "George gets an AI assistant",
            "Erste Group presented new features for its digital banking platform.",
            "Erste Group is piloting AI agents that prepare loan applications and "
            "automatically check supporting documents in its back office.",
            "The pilot runs in Austria and the Czech Republic.",
            "Pilots AI agents in back-office loan processing.",
        ),
    ),
    "dsv.com": (
        _SignalSpec(
            _IA,
            "SHARED_SERVICES",
            _S,
            0.89,
            _NEWS,
            8,
            "DSV integrates DB Schenker",
            "DSV completed the acquisition of DB Schenker.",
            "DSV will merge the back offices of DSV and DB Schenker into its global shared "
            "service centres, harmonising finance and customs processes on one platform.",
            "The integration is expected to take three years.",
            "Merges two back offices into global shared service centres.",
        ),
        _SignalSpec(
            _IA,
            "COST_PROGRAM",
            _M,
            0.8,
            _NEWS,
            8,
            "Synergy target confirmed",
            "DSV gave an update to investors.",
            "DSV expects annual synergies of DKK 9 billion from the DB Schenker integration, "
            "mostly from overlapping administration and IT.",
            "Most synergies are expected by 2028.",
            "Names synergy targets from administration and IT.",
        ),
    ),
    "continental.com": (
        _SignalSpec(
            _IA,
            "INCUMBENT_PROVIDER",
            _M,
            0.8,
            _NEWS,
            45,
            "Continental extends automation partnership",
            "Continental announced a partnership update.",
            "Continental has extended its partnership with a global IT service provider that "
            "runs its automation and AI operations until 2029.",
            "The contract covers all regions.",
            "Names an existing external automation service provider.",
            option_key="SERVICE_PROVIDER",
        ),
    ),
}

# Signals of the software development and quality assurance services, by account domain.
_DELIVERY_SIGNALS: dict[str, tuple[_SignalSpec, ...]] = {
    "commerzbank.de": (
        _SignalSpec(
            _SD,
            "LEGACY_MODERNISATION",
            _S,
            0.92,
            _NEWS,
            10,
            "Commerzbank replaces its core banking platform",
            "Commerzbank outlined its technology plans at its capital markets day.",
            "Commerzbank will replace its decades-old core banking systems with a modern, "
            "modular platform and move 80 percent of its applications to the cloud by 2028.",
            "The bank expects lower IT running costs once the migration is complete.",
            "Plans to replace legacy core banking systems.",
        ),
        _SignalSpec(
            _QA,
            "SOFTWARE_FAILURE",
            _M,
            0.84,
            _NEWS,
            24,
            "Online banking outage hits Commerzbank customers",
            "Customers reported problems on Monday morning.",
            "A faulty software update left the online banking and app of Commerzbank unavailable "
            "for several hours, and card payments were delayed.",
            "The bank apologised and said the update had been rolled back.",
            "Reports a faulty release that affected customers.",
        ),
        _SignalSpec(
            _QA,
            "COMPLIANCE_TESTING",
            _M,
            0.78,
            _PUBLICATION,
            50,
            "Digital operational resilience at Commerzbank",
            "Commerzbank describes its resilience framework.",
            "Under DORA, Commerzbank tests the resilience of its critical ICT systems every year, "
            "including scenario-based tests of its payment applications.",
            "Results are reported to the Board of Managing Directors.",
            "Must run DORA resilience testing on its critical systems.",
        ),
    ),
    "dbschenker.com": (
        _SignalSpec(
            _SD,
            "DIGITAL_PRODUCT",
            _S,
            0.9,
            _NEWS,
            7,
            "DB Schenker launches a new customer booking portal",
            "The logistics provider announced new digital services.",
            "DB Schenker is building a new self-service portal and mobile app that lets "
            "customers book, track and pay for land and air freight in one place.",
            "A first version will go live in Germany and Austria next spring.",
            "Builds a new customer portal and mobile app.",
        ),
        _SignalSpec(
            _SD,
            "DEVELOPER_HIRING",
            _M,
            0.82,
            _JOBS,
            3,
            "Senior Full-Stack Developer (m/f/d) - Digital Products",
            "DB Schenker is growing its digital product teams in Essen and Berlin.",
            "We are looking for senior full-stack developers with React and Java experience to "
            "build our next-generation booking and tracking platform.",
            "Hybrid working is possible.",
            "Hires developers for its booking and tracking platform.",
        ),
        _SignalSpec(
            _QA,
            "MAJOR_ROLLOUT",
            _M,
            0.8,
            _NEWS,
            30,
            "DB Schenker moves to a single transport management system",
            "DB Schenker updated its IT roadmap.",
            "DB Schenker is rolling out a single transport management system in 30 countries, "
            "replacing more than a dozen local systems by 2027.",
            "The rollout started in the Nordic countries.",
            "Rolls out a large new system across many countries.",
        ),
    ),
    "airfranceklm.com": (
        _SignalSpec(
            _QA,
            "SOFTWARE_FAILURE",
            _S,
            0.91,
            _NEWS,
            15,
            "Check-in system failure grounds flights",
            "Passengers faced long queues at Paris-Charles de Gaulle and Amsterdam Schiphol.",
            "A failure in the check-in and boarding software of Air France-KLM after a system "
            "update led to more than 150 delayed or cancelled flights on Friday.",
            "The group said it had restored normal operations by the evening.",
            "Reports a software failure that disrupted operations.",
        ),
        _SignalSpec(
            _SD,
            "NEW_TECH_LEADER",
            _M,
            0.85,
            _NEWS,
            40,
            "Air France-KLM appoints new Chief Technology Officer",
            "Air France-KLM announced changes to its executive team.",
            "Air France-KLM has appointed Claire Dubois as Group Chief Technology Officer, "
            "responsible for software engineering and IT platforms across the group.",
            "She previously led engineering at a European travel platform.",
            "Appoints a new CTO.",
        ),
    ),
    "schaeffler.com": (
        _SignalSpec(
            _SD,
            "LEGACY_MODERNISATION",
            _M,
            0.83,
            _PUBLICATION,
            35,
            "Schaeffler moves to SAP S/4HANA",
            "Schaeffler reports on its digital agenda in its annual report.",
            "Schaeffler is migrating its ERP landscape to SAP S/4HANA and retiring more than 200 "
            "custom legacy applications in the process.",
            "The migration will be completed plant by plant.",
            "Modernises its ERP and retires legacy applications.",
        ),
        _SignalSpec(
            _QA,
            "MAJOR_ROLLOUT",
            _S,
            0.88,
            _PUBLICATION,
            35,
            "Go-live plan for the new ERP",
            "Schaeffler describes the next phase of its ERP programme.",
            "The first 40 Schaeffler plants will go live on SAP S/4HANA next year, with "
            "extensive integration and regression testing before each go-live.",
            "The remaining plants follow in waves.",
            "Plans a large ERP go-live with extensive testing.",
        ),
    ),
    "swiss.com": (
        _SignalSpec(
            _QA,
            "TEST_AUTOMATION",
            _M,
            0.81,
            _NEWS,
            20,
            "SWISS modernises its booking platform",
            "SWISS presented its digital roadmap.",
            "SWISS is moving its booking and loyalty applications to weekly releases and wants "
            "to automate most of its regression testing to get there.",
            "The change is part of a wider Lufthansa Group programme.",
            "Plans test automation to support faster releases.",
        ),
        _SignalSpec(
            _QA,
            "QA_HIRING",
            _M,
            0.79,
            _JOBS,
            5,
            "Test Automation Engineer (m/f/d)",
            "SWISS is looking for engineers in Zurich.",
            "You will build automated end-to-end tests for our booking, check-in and loyalty "
            "applications using Playwright and Cypress.",
            "German or French is an advantage.",
            "Hires test automation engineers.",
        ),
    ),
    "lufthansagroup.com": (
        _SignalSpec(
            _SD,
            "EXTERNAL_DELIVERY",
            _M,
            0.8,
            _NEWS,
            45,
            "Lufthansa Group expands nearshore software delivery",
            "Lufthansa Group spoke about its IT sourcing strategy.",
            "Lufthansa Group plans to expand software delivery with nearshore partners in "
            "Eastern Europe to speed up development of its customer apps.",
            "The group wants to reduce time to market for new features.",
            "Plans nearshore partners for software delivery.",
        ),
    ),
    "erstegroup.com": (
        _SignalSpec(
            _SD,
            "DIGITAL_PRODUCT",
            _M,
            0.8,
            _NEWS,
            18,
            "George expands to new markets",
            "Erste Group announced the next steps for its digital platform.",
            "Erste Group will launch new features of its George digital banking app for small "
            "businesses in Croatia and Serbia next year.",
            "The bank serves more than 10 million digital customers.",
            "Builds new features of its digital banking product.",
        ),
        _SignalSpec(
            _QA,
            "COMPLIANCE_TESTING",
            _M,
            0.77,
            _NEWS,
            26,
            "Erste Group tests resilience under DORA",
            "Austrian banks are preparing for threat-led penetration tests.",
            "Erste Group must carry out DORA resilience and threat-led penetration testing of "
            "its critical banking applications in all its core markets.",
            "A programme office coordinates the tests.",
            "Must run DORA resilience testing.",
        ),
    ),
    "continental.com": (
        _SignalSpec(
            _SD,
            "IN_HOUSE_ENGINEERING",
            _S,
            0.88,
            _PUBLICATION,
            30,
            "Software at Continental",
            "Continental describes its software organisation.",
            "Continental employs more than 20,000 software and IT engineers who develop its "
            "vehicle software and business applications in-house.",
            "Its software hubs are in Germany, Romania and India.",
            "Describes a large in-house software engineering organisation.",
        ),
    ),
    "dhl.com": (
        _SignalSpec(
            _QA,
            "QA_HIRING",
            _M,
            0.8,
            _JOBS,
            8,
            "QA Lead - Parcel IT (m/f/d)",
            "DHL Parcel is growing its IT teams in Bonn.",
            "As QA Lead you will set up the test strategy and test automation for our new parcel "
            "sorting and routing software.",
            "You will lead a team of five testers.",
            "Hires a QA lead for new parcel software.",
        ),
    ),
}

# Account domain → its contacts, fictional people at the demo accounts.
_DEMO_CONTACTS: dict[str, tuple[_ContactSpec, ...]] = {
    "lufthansagroup.com": (
        _ContactSpec(
            "Anna Weber", "Head of Global Business Services", ContactPersona.HEAD_OF_SHARED_SERVICES
        ),
        _ContactSpec("Thomas Richter", "Chief Information Officer", ContactPersona.CIO),
    ),
    "dhl.com": (
        _ContactSpec(
            "Katrin Maurer",
            "Chief Process Officer, DHL eCommerce",
            ContactPersona.HEAD_OF_PROCESS_EXCELLENCE,
        ),
        _ContactSpec(
            "Jan de Vries", "VP Customer Service Automation", ContactPersona.HEAD_OF_AUTOMATION
        ),
    ),
    "kuehne-nagel.com": (
        _ContactSpec(
            "Lukas Brunner", "Chief Digital Officer", ContactPersona.HEAD_OF_DIGITAL_TRANSFORMATION
        ),
    ),
    "siemens.com": (
        _ContactSpec(
            "Sabine Krause",
            "Head of Procurement Excellence",
            ContactPersona.HEAD_OF_PROCESS_EXCELLENCE,
        ),
    ),
    "bosch.com": (
        _ContactSpec(
            "Michael Hoffmann",
            "Head of Automation, Global Business Services",
            ContactPersona.HEAD_OF_AUTOMATION,
        ),
        _ContactSpec("Julia Schneider", "Chief Information Security Officer", ContactPersona.CISO),
    ),
    "zf.com": (
        _ContactSpec("Markus Feld", "Chief Information Security Officer", ContactPersona.CISO),
        _ContactSpec(
            "Petra Wagner", "Head of Shared Services Europe", ContactPersona.HEAD_OF_SHARED_SERVICES
        ),
    ),
    "ubs.com": (
        _ContactSpec("David Keller", "Group Chief Operating Officer", ContactPersona.COO),
        _ContactSpec("Laura Meier", "Head of Operational Resilience", ContactPersona.CISO),
    ),
    "allianz.com": (
        _ContactSpec(
            "Stefan Braun",
            "Head of Claims Transformation",
            ContactPersona.HEAD_OF_DIGITAL_TRANSFORMATION,
        ),
    ),
    "zurich.com": (
        _ContactSpec(
            "Elena Brunner", "Group Chief Information Security Officer", ContactPersona.CISO
        ),
    ),
    "erstegroup.com": (
        _ContactSpec("Martin Novak", "Chief Operating Officer", ContactPersona.COO),
    ),
    "dsv.com": (
        _ContactSpec(
            "Mette Larsen",
            "Head of Integration and Shared Services",
            ContactPersona.HEAD_OF_SHARED_SERVICES,
        ),
    ),
    "munichre.com": (
        _ContactSpec("Florian Schmid", "Chief Technology Officer", ContactPersona.CTO),
    ),
    "commerzbank.de": (
        _ContactSpec("Sebastian Lang", "Chief Information Officer", ContactPersona.CIO),
        _ContactSpec("Nina Fischer", "Head of Quality Engineering", ContactPersona.OTHER),
    ),
    "dbschenker.com": (
        _ContactSpec("Oliver Becker", "Head of Digital Products", ContactPersona.CTO),
    ),
    "airfranceklm.com": (
        _ContactSpec("Claire Dubois", "Group Chief Technology Officer", ContactPersona.CTO),
    ),
    "schaeffler.com": (
        _ContactSpec("Andreas Vogel", "Head of ERP Transformation", ContactPersona.CIO),
    ),
    "swiss.com": (_ContactSpec("Laura Frei", "Head of Digital Engineering", ContactPersona.CTO),),
}


def _answer(answer_type: SignalQuestionAnswerType, spec: _SignalSpec) -> dict[str, object]:
    """The classifier answer the finding would have come from, in the keys `map_answer` reads."""
    rest = round(1 - spec.confidence, 2)
    if answer_type is SignalQuestionAnswerType.YES_NO:
        return {"YES": spec.confidence, "NO": rest, spec.strength.value: spec.confidence}
    if answer_type is SignalQuestionAnswerType.CHOICE:
        return {spec.option_key or "": spec.confidence, "NONE_NAMED": rest}
    return {spec.strength.value: spec.confidence, "NONE": rest}


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def _signals_by_domain() -> dict[str, tuple[_SignalSpec, ...]]:
    domains = dict.fromkeys([*_DEMO_SIGNALS, *_DELIVERY_SIGNALS])
    return {
        domain: (*_DEMO_SIGNALS.get(domain, ()), *_DELIVERY_SIGNALS.get(domain, ()))
        for domain in domains
    }


async def _seeded_document_urls(db: AsyncSession) -> set[str]:
    return set(
        (
            await db.execute(select(Document.url).where(Document.url.startswith(DEMO_SIGNAL_HOST)))
        ).scalars()
    )


async def _seeded_contact_urls(db: AsyncSession) -> set[str]:
    return set(
        (
            await db.execute(
                select(Contact.source_url).where(Contact.source_url.startswith(DEMO_SIGNAL_HOST))
            )
        ).scalars()
    )


async def seed_demo_signals_and_contacts(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    now: datetime,
    document_retention_days: int,
    contact_retention_days: int,
) -> None:
    """Adds the demo signals and contacts, one `SUCCEEDED` refresh run per account that carries
    its documents, then scores every active account through `run_score_step` so the scores and
    breakdowns come from the scoring rule. Skips each document and contact already seeded, and
    scores only when it added a document."""
    seeded_documents = await _seeded_document_urls(db)
    seeded_contacts = await _seeded_contact_urls(db)

    services = {
        service.code: service
        for service in (
            await db.execute(select(Service).where(Service.status == ServiceStatus.ACTIVE))
        ).scalars()
    }
    questions = {
        (question.service_id, question.key): question
        for question in (
            await db.execute(
                select(SignalQuestion).where(SignalQuestion.status == SignalQuestionStatus.ACTIVE)
            )
        ).scalars()
    }
    accounts = {
        account.domain: account
        for account in (
            await db.execute(select(Account).where(Account.status == AccountStatus.ACTIVE))
        ).scalars()
    }

    added = False
    for domain, all_specs in _signals_by_domain().items():
        account = accounts.get(domain)
        specs = [
            spec
            for spec in all_specs
            if spec.service_code in services
            and f"{DEMO_SIGNAL_HOST}/{domain}/{_slug(spec.title)}" not in seeded_documents
        ]
        if account is None or not specs:
            continue
        added = True
        run = PipelineRun(
            kind=PipelineRunKind.ACCOUNT_REFRESH,
            trigger=PipelineRunTrigger.USER,
            account_id=account.id,
            status=PipelineRunStatus.SUCCEEDED,
            stage=PipelineRunStage.SCORE,
            progress={"documents_kept": len(specs), "findings_created": len(specs)},
            errors=[],
            requested_by=actor_id,
            started_at=now,
            finished_at=now,
        )
        db.add(run)
        await db.flush()
        for spec in specs:
            service = services[spec.service_code]
            question = questions[(service.id, spec.question_key)]
            published_at = now - timedelta(days=spec.days_ago)
            url = f"{DEMO_SIGNAL_HOST}/{domain}/{_slug(spec.title)}"
            document = Document(
                account_id=account.id,
                run_id=run.id,
                plugin_code=_PLUGIN_BY_SOURCE_TYPE[spec.source_type],
                source_type=spec.source_type,
                url=url,
                canonical_url=url,
                title=spec.title,
                language=spec.language,
                published_at=published_at,
                fetched_at=now,
                content_hash=hashlib.sha256(spec.text.encode()).hexdigest(),
                text=spec.text,
                duplicate_of_id=None,
                purge_after=(now + timedelta(days=document_retention_days)).date(),
                purged_at=None,
            )
            db.add(document)
            await db.flush()
            db.add(
                DocumentTriage(
                    document_id=document.id,
                    classifier=DocumentTriageClassifier.LLM,
                    about_account_p=0.97,
                    service_relevance={str(service.id): spec.confidence},
                    outcome=DocumentTriageOutcome.KEPT,
                )
            )
            chunk = Chunk(
                document_id=document.id,
                ordinal=0,
                char_start=0,
                char_end=len(spec.text),
                section=None,
                text=spec.text,
                embedding=None,
            )
            db.add(chunk)
            await db.flush()
            classification = Classification(
                chunk_id=chunk.id,
                question_id=question.id,
                question_revision=question.revision,
                run_id=run.id,
                classifier=DocumentTriageClassifier.LLM,
                answer=_answer(question.answer_type, spec),
                p_positive=spec.confidence,
                escalated=False,
                strength=spec.strength,
                status=ClassificationStatus.POSITIVE,
                evidence_retried=False,
            )
            db.add(classification)
            await db.flush()
            db.add(
                Finding(
                    account_id=account.id,
                    question_id=question.id,
                    question_revision=question.revision,
                    classification_id=classification.id,
                    chunk_id=chunk.id,
                    strength=spec.strength,
                    confidence=spec.confidence,
                    decided_by=FindingDecidedBy.LLM,
                    option_key=spec.option_key,
                    quote=spec.quote,
                    quote_en=spec.quote_en,
                    rationale=spec.rationale,
                    observed_at=published_at,
                    status=FindingStatus.ACTIVE,
                )
            )

    for domain, contacts in _DEMO_CONTACTS.items():
        account = accounts.get(domain)
        if account is None:
            continue
        for contact in contacts:
            source_url = f"{DEMO_SIGNAL_HOST}/{domain}/people/{_slug(contact.full_name)}"
            if source_url in seeded_contacts:
                continue
            db.add(
                Contact(
                    account_id=account.id,
                    full_name=contact.full_name,
                    job_title=contact.job_title,
                    persona=contact.persona,
                    persona_origin=ContactPersonaOrigin.MANUAL,
                    source_url=source_url,
                    retain_until=(now + timedelta(days=contact_retention_days)).date(),
                )
            )

    if not added:
        await db.commit()
        return

    rescore = PipelineRun(
        kind=PipelineRunKind.RESCORE,
        trigger=PipelineRunTrigger.USER,
        status=PipelineRunStatus.SUCCEEDED,
        stage=PipelineRunStage.SCORE,
        progress={},
        errors=[],
        requested_by=actor_id,
        started_at=now,
        finished_at=now,
    )
    db.add(rescore)
    await db.flush()
    await run_score_step(
        db,
        run=rescore,
        alert_max_age_days=WorkerSettings.model_fields["alert_max_age_days"].default,
        now=now,
    )
    await db.commit()
