"""Entry point `leadradar-seed-demo` ([Seeding](/architecture/overview.md#runtime),
`S-RUN-03`): loads the whole [Demo dataset](/architecture/overview.md#demo-dataset) into an
empty database, in the order the Seeding paragraph states it - users, industries, markets,
source plug-ins, services with their questions and active scoring versions, and the accounts
with their sources and parent links - reusing the same capability functions the API routes call,
so the same rules, audit rows and idempotent-write behaviour apply. It never fetches.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.commands import AccountUpdateData, import_accounts, update_account
from leadradar.audit.events import append_audit_event
from leadradar.auth.users import UserCreateData, create_user
from leadradar.clock import build_clock
from leadradar.configuration.commands import (
    create_industry,
    create_market,
    create_question,
    create_service,
    save_scoring_draft,
)
from leadradar.core.account_identity import normalise_name
from leadradar.core.account_import import parse_csv_rows, parse_import_row
from leadradar.core.enums import (
    AccountRelationshipStatus,
    AccountSourceKind,
    AccountSourceOrigin,
    AccountStatus,
    AppUserRole,
    AppUserStatus,
    AuditAction,
    DiscoveryCandidateOrigin,
    DiscoveryCandidateStatus,
    DocumentSourceType,
    FindingStrength,
    IndustryStatus,
    MarketStatus,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    ScoringConfigStatus,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.core.scoring.fit import fit
from leadradar.core.scoring.settings import (
    Disqualifier,
    DisqualifierKind,
    ICPCriterion,
    ICPCriterionKind,
    QuestionSetting,
    ScoringSettings,
    WeightLevel,
    default_scoring_settings,
)
from leadradar.db.models.accounts import (
    Account,
    AccountAlias,
    AccountSource,
    DiscoveryCandidate,
)
from leadradar.db.models.configuration import (
    Industry,
    Market,
    ScoringConfig,
    Service,
    SignalQuestion,
)
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import PipelineRun, SourcePlugin
from leadradar.db.session import build_engine
from leadradar.discovery.commands import reject_candidate
from leadradar.logs import configure_json_logging
from leadradar.settings import ApiSettings

logger = logging.getLogger(__name__)


class SeedSettings(ApiSettings):
    """Adds the two demo passwords, required only by this entry point. `PASSWORD_MIN_LENGTH` is
    enforced once, by `auth.users.create_user` (`seed_demo_users` passes it through), not
    repeated here."""

    seed_admin_password: SecretStr
    seed_sales_password: SecretStr


# --- Users -------------------------------------------------------------------------------------

# [Demo dataset](/architecture/overview.md#demo-dataset) Users. Exported so `leadradar-refresh-
# demo` ([Seeding](/architecture/overview.md#runtime)) can look up the Admin it acts as, without
# a second literal of the same address.
DEMO_ADMIN_EMAIL = "admin@leadradar.local"
DEMO_SALES_EMAIL = "sales@leadradar.local"
# The demo user of each role, which the demo sign-in `API-78` signs in as.
DEMO_USER_EMAILS: dict[AppUserRole, str] = {
    AppUserRole.ADMIN: DEMO_ADMIN_EMAIL,
    AppUserRole.SALES: DEMO_SALES_EMAIL,
}

# Email, role, and the settings field holding its password. Display name is the email's local
# part (G2). The admin comes first: every later step needs its id as the actor of a write the
# seed makes on its behalf.
_DEMO_USERS = (
    (DEMO_ADMIN_EMAIL, AppUserRole.ADMIN, "seed_admin_password"),
    (DEMO_SALES_EMAIL, AppUserRole.SALES, "seed_sales_password"),
)


async def seed_demo_users(db: AsyncSession, settings: SeedSettings) -> uuid.UUID:
    """Creates the Admin and the Sales user of the demo dataset, with a null actor (seeding,
    G4). Returns the Admin's id, the actor every later seeding step writes as."""
    now = build_clock(settings)()
    admin_id: uuid.UUID | None = None
    for email, role, password_field in _DEMO_USERS:
        password = getattr(settings, password_field).get_secret_value()
        display_name = email.split("@", 1)[0]
        user = await create_user(
            db,
            actor_id=None,
            data=UserCreateData(
                email=email, display_name=display_name, role=role, password=password
            ),
            now=now,
            password_min_length=settings.password_min_length,
        )
        if role == AppUserRole.ADMIN:
            admin_id = user.id
    assert admin_id is not None, "the demo users always include one Admin"
    return admin_id


# --- Industries and markets ---------------------------------------------------------------------

# [Demo dataset](/architecture/overview.md#demo-dataset) Industries: code, label.
_DEMO_INDUSTRIES = (
    ("AEROSPACE_AVIATION", "Aviation and aerospace"),
    ("AUTOMOTIVE", "Automotive"),
    ("BANKING", "Banking"),
    ("INSURANCE", "Insurance"),
    ("LOGISTICS_TRANSPORT", "Logistics and transport"),
    ("MANUFACTURING", "Manufacturing"),
    ("ENERGY_UTILITIES", "Energy and utilities"),
    ("TELECOM_MEDIA", "Telecom and media"),
    ("RETAIL_CONSUMER", "Retail and consumer goods"),
    ("HEALTHCARE_PHARMA", "Healthcare and pharma"),
    ("PUBLIC_SECTOR", "Public sector"),
    ("TECHNOLOGY", "Technology"),
    ("PROFESSIONAL_SERVICES", "Professional services"),
    ("OTHER", "Other"),
)

# [Demo dataset](/architecture/overview.md#demo-dataset) Markets: code, name, country codes.
_DEMO_MARKETS = (
    ("DACH", "DACH", ["DE", "AT", "CH"]),
    ("BENELUX", "Benelux", ["BE", "NL", "LU"]),
    ("NORDICS", "Nordics", ["DK", "SE", "NO", "FI"]),
    (
        "EU",
        "European Union",
        [
            "AT",
            "BE",
            "BG",
            "HR",
            "CY",
            "CZ",
            "DK",
            "EE",
            "FI",
            "FR",
            "DE",
            "GR",
            "HU",
            "IE",
            "IT",
            "LV",
            "LT",
            "LU",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SK",
            "SI",
            "ES",
            "SE",
        ],
    ),
)


async def seed_demo_industries(db: AsyncSession, *, actor_id: uuid.UUID, now: datetime) -> None:
    for code, label in _DEMO_INDUSTRIES:
        await create_industry(db, code=code, label=label, actor_id=actor_id, now=now)


async def seed_demo_markets(db: AsyncSession, *, actor_id: uuid.UUID, now: datetime) -> None:
    for code, name, country_codes in _DEMO_MARKETS:
        await create_market(
            db, code=code, name=name, country_codes=country_codes, actor_id=actor_id, now=now
        )


# --- Source plug-ins ---------------------------------------------------------------------------

# [Demo dataset](/architecture/overview.md#demo-dataset) Source plug-ins: code, rate limit per
# minute. No row carries a `daily_quota`. Not written through a capability function: no route
# creates a `source_plugin` row (only `PLUGIN_UPDATED` edits one already seeded), so this is the
# one place the table's rows come from.
_DEMO_SOURCE_PLUGINS: tuple[tuple[SourcePluginCode, int], ...] = (
    (SourcePluginCode.GDELT, 10),
    (SourcePluginCode.RSS, 30),
    (SourcePluginCode.WEBSITE, 30),
    (SourcePluginCode.CAREERS, 30),
    (SourcePluginCode.CRUNCHBASE, 30),
    (SourcePluginCode.NEWSAPI, 30),
    (SourcePluginCode.SERPAPI, 30),
)


async def seed_demo_source_plugins(db: AsyncSession) -> None:
    """One [`source_plugin`](/architecture/sql-store.md#source_plugin) row per plug-in value,
    `enabled`. The entry point checks an existing seed before this insert."""
    for code, rate_limit_per_minute in _DEMO_SOURCE_PLUGINS:
        db.add(
            SourcePlugin(
                code=code,
                enabled=True,
                rate_limit_per_minute=rate_limit_per_minute,
                daily_quota=None,
                last_success_at=None,
                last_error=None,
                last_error_at=None,
            )
        )
    await db.commit()


# --- Services, questions and scoring -------------------------------------------------------------


@dataclass(frozen=True)
class _QuestionSpec:
    """One row of a service's questions table of the [Demo dataset]
    (/architecture/overview.md#demo-dataset): the `signal_question` fields `create_question`
    takes, plus the `weight` and `half_life_days` its scoring draft sets (`create_question`
    itself always joins at weight `MEDIUM`, no half-life)."""

    key: str
    text: str
    answer_type: SignalQuestionAnswerType
    polarity: SignalQuestionPolarity
    source_types: tuple[DocumentSourceType, ...]
    weight: WeightLevel
    hint_terms: tuple[str, ...] = ()
    options: tuple[dict[str, object], ...] | None = None
    half_life_days: int | None = None


@dataclass(frozen=True)
class _ServiceSpec:
    code: str
    name: str
    description: str
    value_proposition: str
    questions: tuple[_QuestionSpec, ...]
    icp_criteria: tuple[ICPCriterion, ...]
    disqualifiers: tuple[Disqualifier, ...]


# The `REGION` ICP criterion's countries, shared by both services ([Demo dataset]
# (/architecture/overview.md#demo-dataset): Cybersecurity's ICP is "REGION (as Intelligent
# Automation; MEDIUM)").
_REGION_COUNTRIES = (
    "DE",
    "AT",
    "CH",
    "NL",
    "BE",
    "LU",
    "FR",
    "IT",
    "DK",
    "SE",
    "NO",
    "FI",
)

# The `INSOLVENT` disqualifier, shared by both services ("Disqualifier: INSOLVENT as Intelligent
# Automation").
_INSOLVENT_DISQUALIFIER = Disqualifier(
    key="INSOLVENT",
    label="In insolvency",
    kind=DisqualifierKind.SIGNAL,
    question_key="INSOLVENCY",
    min_strength=FindingStrength.MEDIUM,
)

# The `INSOLVENCY` question, shared in text and shape by both services' tables.
_INSOLVENCY_QUESTION = _QuestionSpec(
    key="INSOLVENCY",
    text="Is the company in insolvency, restructuring under creditor protection, or being "
    "wound up?",
    answer_type=SignalQuestionAnswerType.YES_NO,
    polarity=SignalQuestionPolarity.NEGATIVE,
    source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PROFILE),
    weight=WeightLevel.NONE,
    hint_terms=("insolvency", "Insolvenz"),
)

_INTELLIGENT_AUTOMATION = _ServiceSpec(
    code="INTELLIGENT_AUTOMATION",
    name="Intelligent Automation",
    description=(
        "Automating business processes end to end with RPA, AI, agentic AI and process "
        "mining, from discovery to operation."
    ),
    value_proposition=(
        "Orange Systems designs, builds and runs automation that removes manual work from "
        "finance, operations and customer processes, with measurable savings within months."
    ),
    questions=(
        _QuestionSpec(
            key="COST_PROGRAM",
            text="Does the company announce or run a cost-reduction, efficiency or "
            "profitability programme?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.HIGH,
            hint_terms=(
                "cost reduction",
                "efficiency programme",
                "savings target",
                "Kostensenkung",
                "Effizienzprogramm",
            ),
        ),
        _QuestionSpec(
            key="DIGITAL_TRANSFORMATION",
            text="Does the company describe a digital transformation initiative that changes "
            "how its processes run?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.MEDIUM,
            hint_terms=("digital transformation", "Digitalisierung"),
        ),
        _QuestionSpec(
            key="AUTOMATION_INITIATIVE",
            text="Does the company run or plan AI, RPA, agentic AI or process-mining projects "
            "in its business processes?",
            answer_type=SignalQuestionAnswerType.SCALE,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.HIGH,
            hint_terms=(
                "RPA",
                "process mining",
                "agentic AI",
                "intelligent automation",
                "KI-Agenten",
            ),
        ),
        _QuestionSpec(
            key="AUTOMATION_HIRING",
            text="Is the company hiring for RPA development, automation engineering, AI, "
            "business analysis or process excellence?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.JOB_POSTING,),
            weight=WeightLevel.MEDIUM,
        ),
        _QuestionSpec(
            key="NEW_EXECUTIVE",
            text="Has the company appointed a new CIO, COO, CDO or head of transformation, "
            "automation or process excellence?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(
                DocumentSourceType.NEWS,
                DocumentSourceType.COMPANY_PUBLICATION,
                DocumentSourceType.COMPANY_PROFILE,
            ),
            weight=WeightLevel.MEDIUM,
            hint_terms=("appointed", "new CIO", "neuer CIO"),
            half_life_days=180,
        ),
        _QuestionSpec(
            key="SHARED_SERVICES",
            text="Does the company consolidate processes or build or expand shared service "
            "centres?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.MEDIUM,
            hint_terms=("shared services", "global business services", "consolidation"),
        ),
        _QuestionSpec(
            key="IN_HOUSE_AUTOMATION",
            text="Does the company describe a strong in-house automation or AI capability, "
            "such as its own automation centre of excellence or platform?",
            answer_type=SignalQuestionAnswerType.SCALE,
            polarity=SignalQuestionPolarity.NEGATIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.MEDIUM,
            hint_terms=("centre of excellence", "in-house"),
        ),
        _QuestionSpec(
            key="INCUMBENT_PROVIDER",
            text="Does the company name an existing external provider for automation or AI "
            "services?",
            answer_type=SignalQuestionAnswerType.CHOICE,
            polarity=SignalQuestionPolarity.NEGATIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.LOW,
            hint_terms=("partnership", "UiPath", "Celonis"),
            options=(
                {"key": "NONE_NAMED", "label": "None named", "strength": "NONE"},
                {"key": "PLATFORM_VENDOR", "label": "Platform vendor", "strength": "WEAK"},
                {"key": "SERVICE_PROVIDER", "label": "Service provider", "strength": "MEDIUM"},
                {
                    "key": "STRATEGIC_PARTNERSHIP",
                    "label": "Strategic partnership",
                    "strength": "STRONG",
                },
            ),
        ),
        _INSOLVENCY_QUESTION,
    ),
    icp_criteria=(
        ICPCriterion(
            key="SECTOR",
            kind=ICPCriterionKind.INDUSTRY,
            weight=WeightLevel.HIGH,
            values=[
                "AEROSPACE_AVIATION",
                "LOGISTICS_TRANSPORT",
                "MANUFACTURING",
                "AUTOMOTIVE",
                "BANKING",
                "INSURANCE",
            ],
        ),
        ICPCriterion(
            key="REGION",
            kind=ICPCriterionKind.GEOGRAPHY,
            weight=WeightLevel.MEDIUM,
            values=list(_REGION_COUNTRIES),
        ),
        ICPCriterion(
            key="SIZE", kind=ICPCriterionKind.EMPLOYEE_RANGE, weight=WeightLevel.MEDIUM, min=5000
        ),
        ICPCriterion(
            key="COMPLEXITY",
            kind=ICPCriterionKind.OPERATIONAL_COMPLEXITY,
            weight=WeightLevel.LOW,
            values=["MEDIUM", "HIGH"],
        ),
    ),
    disqualifiers=(
        Disqualifier(
            key="OUTSIDE_EUROPE",
            label="Outside the target region",
            kind=DisqualifierKind.ICP_MISMATCH,
            criterion_key="REGION",
        ),
        _INSOLVENT_DISQUALIFIER,
    ),
)

_CYBERSECURITY = _ServiceSpec(
    code="CYBERSECURITY",
    name="Cybersecurity services",
    description=(
        "Security assessments, managed detection and response, and regulatory readiness for "
        "NIS2, DORA and the Cyber Resilience Act."
    ),
    value_proposition=(
        "Orange Systems assesses, strengthens and monitors a company's security posture and "
        "gets it audit-ready for European regulation."
    ),
    questions=(
        _QuestionSpec(
            key="SECURITY_INCIDENT",
            text="Does the text report a cyber-attack, data breach, ransomware or major IT "
            "outage at the company?",
            answer_type=SignalQuestionAnswerType.SCALE,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS,),
            weight=WeightLevel.HIGH,
            hint_terms=("cyber attack", "data breach", "ransomware", "Cyberangriff"),
            half_life_days=120,
        ),
        _QuestionSpec(
            key="REGULATION_PRESSURE",
            text="Is the company preparing for or subject to security regulation such as "
            "NIS2, DORA or the Cyber Resilience Act?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.MEDIUM,
            hint_terms=("NIS2", "DORA", "Cyber Resilience Act", "KRITIS"),
        ),
        _QuestionSpec(
            key="SECURITY_HIRING",
            text="Is the company hiring security roles such as SOC analysts, security "
            "engineers, a CISO or GRC specialists?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.JOB_POSTING,),
            weight=WeightLevel.MEDIUM,
        ),
        _QuestionSpec(
            key="NEW_CISO",
            text="Has the company appointed a new CISO or head of security?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(
                DocumentSourceType.NEWS,
                DocumentSourceType.COMPANY_PUBLICATION,
                DocumentSourceType.COMPANY_PROFILE,
            ),
            weight=WeightLevel.MEDIUM,
            hint_terms=("CISO", "head of security"),
            half_life_days=180,
        ),
        _QuestionSpec(
            key="CLOUD_MIGRATION",
            text="Does the company run a large cloud migration or IT modernisation programme?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.POSITIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.LOW,
            hint_terms=("cloud migration", "IT modernisation"),
        ),
        _QuestionSpec(
            key="MANAGED_SOC_IN_PLACE",
            text="Does the company name an existing managed security or SOC provider?",
            answer_type=SignalQuestionAnswerType.YES_NO,
            polarity=SignalQuestionPolarity.NEGATIVE,
            source_types=(DocumentSourceType.NEWS, DocumentSourceType.COMPANY_PUBLICATION),
            weight=WeightLevel.MEDIUM,
            hint_terms=("managed SOC", "MDR"),
        ),
        _INSOLVENCY_QUESTION,
    ),
    icp_criteria=(
        ICPCriterion(
            key="SECTOR",
            kind=ICPCriterionKind.INDUSTRY,
            weight=WeightLevel.HIGH,
            values=[
                "BANKING",
                "INSURANCE",
                "ENERGY_UTILITIES",
                "HEALTHCARE_PHARMA",
                "MANUFACTURING",
                "AUTOMOTIVE",
                "LOGISTICS_TRANSPORT",
                "AEROSPACE_AVIATION",
            ],
        ),
        ICPCriterion(
            key="REGION",
            kind=ICPCriterionKind.GEOGRAPHY,
            weight=WeightLevel.MEDIUM,
            values=list(_REGION_COUNTRIES),
        ),
        ICPCriterion(
            key="SIZE", kind=ICPCriterionKind.EMPLOYEE_RANGE, weight=WeightLevel.MEDIUM, min=1000
        ),
    ),
    disqualifiers=(_INSOLVENT_DISQUALIFIER,),
)

_DEMO_SERVICES = (_INTELLIGENT_AUTOMATION, _CYBERSECURITY)


async def _activate_first_scoring_draft(
    db: AsyncSession, *, scoring_config_id: uuid.UUID, now: datetime
) -> None:
    """Promotes a freshly seeded service's version-1 draft straight to `ACTIVE` ([Demo dataset]
    (/architecture/overview.md#demo-dataset): "active scoring versions"). The general activation
    capability (`API-18`) also re-validates, retires a previous active version and enqueues a
    `RESCORE` run - another task's, not built yet; none of that applies to a brand-new version 1
    with no predecessor and, at this point in seeding, no account to rescore, so this seed-only
    step does only what version 1 needs: flip the status and record `SCORING_ACTIVATED`."""
    draft = (
        await db.execute(
            select(ScoringConfig).where(ScoringConfig.id == scoring_config_id).with_for_update()
        )
    ).scalar_one()
    assert draft.status == ScoringConfigStatus.DRAFT
    draft.status = ScoringConfigStatus.ACTIVE
    draft.activated_at = now
    draft.activated_by = None
    await append_audit_event(
        db,
        action=AuditAction.SCORING_ACTIVATED,
        occurred_at=now,
        actor_id=None,
        entity_type="scoring_config",
        entity_id=draft.id,
        payload={"version": draft.version},
    )
    await db.commit()


async def seed_demo_services(db: AsyncSession, *, actor_id: uuid.UUID, now: datetime) -> None:
    """Creates each service of the [Demo dataset](/architecture/overview.md#demo-dataset) with
    its questions (`API-08`, `API-12`), then replaces the auto-created draft's settings with the
    service's ICP criteria, question weights and half-lives, and disqualifiers (`API-17`) before
    activating it as version 1."""
    for spec in _DEMO_SERVICES:
        service = await create_service(
            db,
            code=spec.code,
            name=spec.name,
            description=spec.description,
            value_proposition=spec.value_proposition,
            actor_id=actor_id,
            now=now,
        )
        for question in spec.questions:
            await create_question(
                db,
                service_id=service.id,
                key=question.key,
                text=question.text,
                answer_type=question.answer_type,
                options=list(question.options) if question.options is not None else None,
                polarity=question.polarity,
                source_types=list(question.source_types),
                hint_terms=list(question.hint_terms),
                actor_id=actor_id,
                now=now,
            )

        document = default_scoring_settings().model_copy(
            update={
                "icp_criteria": list(spec.icp_criteria),
                "questions": [
                    QuestionSetting(
                        question_key=question.key,
                        weight=question.weight,
                        half_life_days=question.half_life_days,
                    )
                    for question in spec.questions
                ],
                "disqualifiers": list(spec.disqualifiers),
            }
        )
        saved = await save_scoring_draft(
            db,
            service_id=service.id,
            settings=document,
            change_note=None,
            actor_id=actor_id,
            now=now,
        )
        await _activate_first_scoring_draft(db, scoring_config_id=saved.summary.id, now=now)


# --- Accounts ------------------------------------------------------------------------------------

# [Demo dataset](/architecture/overview.md#demo-dataset) Accounts: the one non-empty `Parent`
# cell, by domain. The [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) shape
# has no parent column, so the link is made after import, as `API-24` would.
_DEMO_PARENT_DOMAINS: dict[str, str] = {"swiss.com": "lufthansagroup.com"}


class DemoAccountFileMissing(Exception):
    """The demo account file the [Demo dataset](/architecture/overview.md#demo-dataset) names is
    not at `FIXTURE_DIR/demo_accounts.csv`. The team collects it separately; seeding never
    invents account data, so it fails loudly instead."""


async def _account_id_by_domain(db: AsyncSession, domain: str) -> uuid.UUID:
    account_id = (await db.execute(select(Account.id).where(Account.domain == domain))).scalar_one()
    return account_id


async def seed_demo_accounts(
    db: AsyncSession, *, settings: SeedSettings, actor_id: uuid.UUID, now: datetime
) -> None:
    """Imports the [demo account file](/architecture/overview.md#demo-dataset) through
    `import_accounts` (`API-22`), then links the one account of the table with a `Parent` to it
    (`API-24`). Raises `DemoAccountFileMissing` when the file is not there yet."""
    path = settings.fixture_dir / "demo_accounts.csv"
    if not path.is_file():
        raise DemoAccountFileMissing(
            f"No demo account file at {path}. Add it before running make seed-demo."
        )
    file_text = path.read_text(encoding="utf-8")

    result = await import_accounts(
        db,
        file_text=file_text,
        dry_run=False,
        import_max_rows=settings.import_max_rows,
        actor_id=actor_id,
        now=now,
    )
    if result.created != len(result.rows):
        raise DemoSeedMismatch(
            "The demo account import did not create every row; check invalid or duplicate accounts."
        )

    for child_domain, parent_domain in _DEMO_PARENT_DOMAINS.items():
        child_id = await _account_id_by_domain(db, child_domain)
        parent_id = await _account_id_by_domain(db, parent_domain)
        await update_account(
            db,
            account_id=child_id,
            data=AccountUpdateData(parent_account_id=parent_id),
            actor_id=actor_id,
            now=now,
        )


# --- Relationship statuses and suggested accounts ------------------------------------------------

_DEMO_RELATIONSHIP_STATUSES: dict[str, AccountRelationshipStatus] = {
    "siemens.com": AccountRelationshipStatus.CLIENT,
    "allianz.com": AccountRelationshipStatus.CLIENT,
    "munichre.com": AccountRelationshipStatus.CLIENT,
    "continental.com": AccountRelationshipStatus.CLIENT,
    "commerzbank.de": AccountRelationshipStatus.PAST_CLIENT,
    "airfranceklm.com": AccountRelationshipStatus.PAST_CLIENT,
    "schaeffler.com": AccountRelationshipStatus.PAST_CLIENT,
    "bosch.com": AccountRelationshipStatus.IN_TALKS,
    "ubs.com": AccountRelationshipStatus.IN_TALKS,
    "kuehne-nagel.com": AccountRelationshipStatus.IN_TALKS,
    "erstegroup.com": AccountRelationshipStatus.IN_TALKS,
    "zf.com": AccountRelationshipStatus.IN_TALKS,
    "generali.com": AccountRelationshipStatus.DO_NOT_CONTACT,
    "rbinternational.com": AccountRelationshipStatus.DO_NOT_CONTACT,
}


@dataclass(frozen=True)
class _CandidateSpec:
    service_code: str
    name: str
    domain: str | None
    country_code: str
    industry: str
    employee_count: int | None
    reject_reason: str | None = None


_DEMO_CANDIDATES = (
    _CandidateSpec(
        "INTELLIGENT_AUTOMATION", "Hapag-Lloyd", "hlag.com", "DE", "LOGISTICS_TRANSPORT", 14000
    ),
    _CandidateSpec("INTELLIGENT_AUTOMATION", "BASF", "basf.com", "DE", "MANUFACTURING", 112000),
    _CandidateSpec("INTELLIGENT_AUTOMATION", "ING Group", "ing.com", "NL", "BANKING", 60000),
    _CandidateSpec("INTELLIGENT_AUTOMATION", "Swiss Re", "swissre.com", "CH", "INSURANCE", 14000),
    _CandidateSpec(
        "INTELLIGENT_AUTOMATION", "Example Logistik", None, "DE", "LOGISTICS_TRANSPORT", None
    ),
    _CandidateSpec(
        "INTELLIGENT_AUTOMATION",
        "Mahle",
        "mahle.com",
        "DE",
        "AUTOMOTIVE",
        72000,
        reject_reason="Already works with a strategic automation partner.",
    ),
    _CandidateSpec("CYBERSECURITY", "E.ON", "eon.com", "DE", "ENERGY_UTILITIES", 72000),
    _CandidateSpec(
        "CYBERSECURITY", "Fresenius", "fresenius.com", "DE", "HEALTHCARE_PHARMA", 190000
    ),
    _CandidateSpec("CYBERSECURITY", "Nordea", "nordea.com", "FI", "BANKING", 30000),
)


async def seed_demo_relationships_and_suggestions(
    db: AsyncSession, *, actor_id: uuid.UUID, now: datetime
) -> None:
    """Sets the [demo dataset](/architecture/overview.md#demo-dataset)'s relationship statuses
    (`API-24`) and adds its suggested accounts, one `SUCCEEDED` discovery run per seeded service.
    Does nothing once a seeded service has a discovery candidate, so a user's later changes stay."""
    service_codes = {spec.code for spec in _DEMO_SERVICES}
    services = {
        service.code: service
        for service in (
            await db.execute(select(Service).where(Service.code.in_(service_codes)))
        ).scalars()
    }
    already_seeded = (
        await db.execute(
            select(DiscoveryCandidate.id)
            .where(DiscoveryCandidate.service_id.in_([s.id for s in services.values()]))
            .limit(1)
        )
    ).first()
    if already_seeded is not None:
        return

    for domain, relationship_status in _DEMO_RELATIONSHIP_STATUSES.items():
        await update_account(
            db,
            account_id=await _account_id_by_domain(db, domain),
            data=AccountUpdateData(relationship_status=relationship_status),
            actor_id=actor_id,
            now=now,
        )

    admin = (await db.execute(select(AppUser).where(AppUser.id == actor_id))).scalar_one()
    for code, service in services.items():
        config = (
            await db.execute(
                select(ScoringConfig).where(
                    ScoringConfig.service_id == service.id,
                    ScoringConfig.status == ScoringConfigStatus.ACTIVE,
                )
            )
        ).scalar_one()
        settings = ScoringSettings.model_validate(config.settings)
        icp_criteria = [criterion.model_dump() for criterion in settings.icp_criteria]
        specs = [spec for spec in _DEMO_CANDIDATES if spec.service_code == code]
        run = PipelineRun(
            kind=PipelineRunKind.DISCOVERY,
            trigger=PipelineRunTrigger.USER,
            service_id=service.id,
            status=PipelineRunStatus.SUCCEEDED,
            stage=PipelineRunStage.SCORE,
            progress={
                "documents_kept": 0,
                "organisations_found": len(specs),
                "candidates": len(specs),
            },
            errors=[],
            requested_by=actor_id,
            started_at=now,
            finished_at=now,
        )
        db.add(run)
        await db.flush()
        rejected: list[tuple[DiscoveryCandidate, str]] = []
        for spec in specs:
            attributes: dict[str, object] = {
                "country_code": spec.country_code,
                "industry": spec.industry,
                "employee_count": spec.employee_count,
                "revenue_eur": None,
                "operational_complexity": None,
            }
            candidate = DiscoveryCandidate(
                service_id=service.id,
                run_id=run.id,
                name=spec.name,
                normalised_name=normalise_name(spec.name),
                domain=spec.domain,
                country_code=spec.country_code,
                industry=spec.industry,
                employee_count=spec.employee_count,
                origin=DiscoveryCandidateOrigin.CRUNCHBASE_SEARCH,
                document_id=None,
                quote=None,
                fit_estimate=fit(
                    attributes=attributes,
                    icp_criteria=icp_criteria,
                    weight_values=settings.weight_values,
                    unknown_match=settings.unknown_match,
                ).value,
                status=DiscoveryCandidateStatus.PENDING,
                decided_by=None,
                decided_at=None,
                reject_reason=None,
                account_id=None,
            )
            db.add(candidate)
            if spec.reject_reason is not None:
                rejected.append((candidate, spec.reject_reason))
        await db.commit()
        for candidate, reason in rejected:
            await reject_candidate(
                db, candidate_id=candidate.id, reason=reason, principal=admin, now=now
            )


# --- Entry point ---------------------------------------------------------------------------------


class DemoSeedMismatch(Exception):
    """An existing demo seed is incomplete or differs from the declared dataset."""


def _seeded_or_enriched(stored: object, seeded: object) -> bool:
    """Whether a stored attribute is the seed's: equal to the seeded value, or any value when the
    demo file leaves it empty, since a refresh's profile enrichment may fill it
    ([Account attributes](/architecture/rules.md#account-attributes))."""
    return seeded is None or stored == seeded


async def _existing_seed_matches(db: AsyncSession, settings: SeedSettings) -> bool:
    """Return whether a complete demo seed is already present, without writing anything.

    Other application data is allowed; only the identities owned by this seed are checked.
    A partial seed is rejected before any of the seed's committing steps can run.
    """
    path = settings.fixture_dir / "demo_accounts.csv"
    if not path.is_file():
        raise DemoAccountFileMissing(f"No demo account file at {path}. Add it before seeding.")
    rows = [
        parse_import_row(line, raw, frozenset(code for code, _ in _DEMO_INDUSTRIES))
        for line, raw in enumerate(parse_csv_rows(path.read_text(encoding="utf-8")), start=2)
    ]
    if any(row.errors for row in rows):
        raise DemoSeedMismatch("The demo account file has invalid rows.")
    domains = {row.domain for row in rows}
    if len(domains) != len(rows):
        raise DemoSeedMismatch("The demo account file has duplicate domains.")

    users = {
        user.email: user
        for user in (
            await db.execute(select(AppUser).where(AppUser.email.in_([u[0] for u in _DEMO_USERS])))
        ).scalars()
    }
    industries = {row.code: row for row in (await db.execute(select(Industry))).scalars()}
    markets = {row.code: row for row in (await db.execute(select(Market))).scalars()}
    plugins = {row.code: row for row in (await db.execute(select(SourcePlugin))).scalars()}
    services = {row.code: row for row in (await db.execute(select(Service))).scalars()}
    accounts = {
        row.domain: row
        for row in (await db.execute(select(Account).where(Account.domain.in_(domains)))).scalars()
    }
    if not any((users, industries, markets, plugins, services, accounts)):
        return False

    def require(ok: bool, description: str) -> None:
        if not ok:
            raise DemoSeedMismatch(f"Existing demo seed is incomplete or different: {description}.")

    for email, role, _ in _DEMO_USERS:
        user = users.get(email)
        require(
            user is not None
            and user.display_name == email.split("@", 1)[0]
            and user.role == role
            and user.status == AppUserStatus.ACTIVE,
            f"user {email}",
        )
    for code, label in _DEMO_INDUSTRIES:
        industry = industries.get(code)
        require(
            industry is not None
            and industry.label == label
            and industry.status == IndustryStatus.ACTIVE,
            f"industry {code}",
        )
    for code, name, countries in _DEMO_MARKETS:
        market = markets.get(code)
        require(
            market is not None
            and market.name == name
            and market.country_codes == countries
            and market.status == MarketStatus.ACTIVE,
            f"market {code}",
        )
    for code, rate in _DEMO_SOURCE_PLUGINS:
        plugin = plugins.get(code)
        require(
            plugin is not None
            and plugin.enabled
            and plugin.rate_limit_per_minute == rate
            and plugin.daily_quota is None,
            f"source plug-in {code}",
        )
    for spec in _DEMO_SERVICES:
        service = services.get(spec.code)
        require(
            service is not None
            and service.name == spec.name
            and service.description == spec.description
            and service.value_proposition == spec.value_proposition
            and service.status == ServiceStatus.ACTIVE,
            f"service {spec.code}",
        )
        assert service is not None
        questions = {
            question.key: question
            for question in (
                await db.execute(
                    select(SignalQuestion).where(SignalQuestion.service_id == service.id)
                )
            ).scalars()
        }
        require(len(questions) == len(spec.questions), f"questions for {spec.code}")
        for question_spec in spec.questions:
            question = questions.get(question_spec.key)
            require(
                question is not None
                and question.text == question_spec.text
                and question.answer_type == question_spec.answer_type
                and question.options
                == (list(question_spec.options) if question_spec.options is not None else None)
                and question.polarity == question_spec.polarity
                and question.source_types == list(question_spec.source_types)
                and question.hint_terms == list(question_spec.hint_terms)
                and question.revision == 1
                and question.status == SignalQuestionStatus.ACTIVE,
                f"question {spec.code}/{question_spec.key}",
            )
        config = (
            await db.execute(
                select(ScoringConfig).where(
                    ScoringConfig.service_id == service.id,
                    ScoringConfig.version == 1,
                )
            )
        ).scalar_one_or_none()
        require(
            config is not None and config.status == ScoringConfigStatus.ACTIVE,
            f"active scoring version for {spec.code}",
        )
        assert config is not None
        expected_settings = default_scoring_settings().model_copy(
            update={
                "icp_criteria": list(spec.icp_criteria),
                "questions": [
                    QuestionSetting(
                        question_key=q.key, weight=q.weight, half_life_days=q.half_life_days
                    )
                    for q in spec.questions
                ],
                "disqualifiers": list(spec.disqualifiers),
            }
        )
        require(
            config.settings == expected_settings.model_dump(mode="json"),
            f"scoring settings for {spec.code}",
        )
    for account_spec in rows:
        assert account_spec.domain is not None
        account = accounts.get(account_spec.domain)
        require(
            account is not None
            and account.name == account_spec.name
            and account.country_code == account_spec.country_code
            and account.industry == account_spec.industry
            and _seeded_or_enriched(account.employee_count, account_spec.employee_count)
            and _seeded_or_enriched(account.revenue_eur, account_spec.revenue_eur)
            and _seeded_or_enriched(
                account.operational_complexity, account_spec.operational_complexity
            )
            and _seeded_or_enriched(account.linkedin_url, account_spec.linkedin_url)
            and account.notes == account_spec.notes
            and account.status == AccountStatus.ACTIVE,
            f"account {account_spec.domain}",
        )
        assert account is not None
        aliases = {
            alias.alias
            for alias in (
                await db.execute(select(AccountAlias).where(AccountAlias.account_id == account.id))
            ).scalars()
        }
        # A refresh adds `DETECTED` sources
        # ([Source detection](/architecture/rules.md#source-detection)); they are the
        # account's, not the seed's, so only the seeded ones are compared.
        sources = {
            (source.kind, source.url)
            for source in (
                await db.execute(
                    select(AccountSource).where(
                        AccountSource.account_id == account.id,
                        AccountSource.origin != AccountSourceOrigin.DETECTED,
                    )
                )
            ).scalars()
        }
        require(
            aliases == {account_spec.name, *account_spec.aliases},
            f"aliases for {account_spec.domain}",
        )
        require(
            sources
            == {
                (AccountSourceKind.WEBSITE, f"https://{account_spec.domain}/"),
                *((source.kind, source.url) for source in account_spec.sources),
            },
            f"sources for {account_spec.domain}",
        )
        parent_domain = _DEMO_PARENT_DOMAINS.get(account_spec.domain)
        if parent_domain:
            require(parent_domain in accounts, f"parent account {parent_domain}")
        expected_parent = accounts[parent_domain].id if parent_domain else None
        require(account.parent_account_id == expected_parent, f"parent for {account_spec.domain}")
    return True


async def seed_demo_dataset(db: AsyncSession, settings: SeedSettings) -> None:
    """Seed once, or confirm that the existing seed matches; either way, add the relationship
    statuses and suggested accounts while the seeded services have no discovery candidate."""
    now = build_clock(settings)()
    if await _existing_seed_matches(db, settings):
        admin_id = (
            await db.execute(select(AppUser.id).where(AppUser.email == DEMO_ADMIN_EMAIL))
        ).scalar_one()
        await seed_demo_relationships_and_suggestions(db, actor_id=admin_id, now=now)
        return
    admin_id = await seed_demo_users(db, settings)
    await seed_demo_industries(db, actor_id=admin_id, now=now)
    await seed_demo_markets(db, actor_id=admin_id, now=now)
    await seed_demo_source_plugins(db)
    await seed_demo_services(db, actor_id=admin_id, now=now)
    await seed_demo_accounts(db, settings=settings, actor_id=admin_id, now=now)
    await seed_demo_relationships_and_suggestions(db, actor_id=admin_id, now=now)


async def _run(settings: SeedSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await seed_demo_dataset(db, settings)
    finally:
        await engine.dispose()


def run() -> None:
    """`leadradar-seed-demo`: fails loudly (a non-zero exit, one JSON log line) rather than
    seeding a partial or duplicate demo dataset."""
    settings = SeedSettings()
    configure_json_logging(settings.log_level)
    try:
        asyncio.run(_run(settings))
    except Exception:
        logger.exception("Seeding the demo dataset failed")
        sys.exit(1)
    logger.info("Seeded the demo dataset")


if __name__ == "__main__":
    run()
