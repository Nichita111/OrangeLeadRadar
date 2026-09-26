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
from leadradar.core.enums import (
    AppUserRole,
    AuditAction,
    DocumentSourceType,
    FindingStrength,
    ScoringConfigStatus,
    SignalQuestionAnswerType,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.core.scoring_settings import (
    Disqualifier,
    DisqualifierKind,
    ICPCriterion,
    ICPCriterionKind,
    QuestionSetting,
    WeightLevel,
    default_scoring_settings,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import ScoringConfig
from leadradar.db.models.ingestion import SourcePlugin
from leadradar.db.session import build_engine
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
    `enabled`. A second run's unique `code` constraint fails it loudly, matching the users
    step's idempotency."""
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
            f"No demo account file at {path}. Collect it (issue #7) before running make seed-demo."
        )
    file_text = path.read_text(encoding="utf-8")

    await import_accounts(
        db,
        file_text=file_text,
        dry_run=False,
        import_max_rows=settings.import_max_rows,
        actor_id=actor_id,
        now=now,
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


# --- Entry point ---------------------------------------------------------------------------------


async def _run(settings: SeedSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            now = build_clock(settings)()
            admin_id = await seed_demo_users(db, settings)
            await seed_demo_industries(db, actor_id=admin_id, now=now)
            await seed_demo_markets(db, actor_id=admin_id, now=now)
            await seed_demo_source_plugins(db)
            await seed_demo_services(db, actor_id=admin_id, now=now)
            await seed_demo_accounts(db, settings=settings, actor_id=admin_id, now=now)
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
