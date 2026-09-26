"""Closed sets of the SQL store, one `enum.StrEnum` per owning column.

Each class is named after the column that owns it in
[sql-store.md](/architecture/sql-store.md); a column that reuses another
column's enum imports that class instead of redefining it. This module has
no I/O.
"""

from __future__ import annotations

from enum import StrEnum


class AppUserRole(StrEnum):
    """`app_user.role`."""

    SALES = "SALES"
    ADMIN = "ADMIN"


class AppUserStatus(StrEnum):
    """`app_user.status`."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class ServiceStatus(StrEnum):
    """`service.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SignalQuestionAnswerType(StrEnum):
    """`signal_question.answer_type`."""

    YES_NO = "YES_NO"
    SCALE = "SCALE"
    CHOICE = "CHOICE"


class SignalQuestionPolarity(StrEnum):
    """`signal_question.polarity`."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class SignalQuestionStatus(StrEnum):
    """`signal_question.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ScoringConfigStatus(StrEnum):
    """`scoring_config.status`."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class IndustryStatus(StrEnum):
    """`industry.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MarketStatus(StrEnum):
    """`market.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AccountOperationalComplexity(StrEnum):
    """`account.operational_complexity`."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AccountOrigin(StrEnum):
    """`account.origin`."""

    IMPORTED = "IMPORTED"
    MANUAL = "MANUAL"
    DISCOVERED = "DISCOVERED"


class AccountStatus(StrEnum):
    """`account.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AccountSourceKind(StrEnum):
    """`account_source.kind`."""

    WEBSITE = "WEBSITE"
    NEWSROOM = "NEWSROOM"
    INVESTOR_RELATIONS = "INVESTOR_RELATIONS"
    CAREERS = "CAREERS"
    RSS_FEED = "RSS_FEED"


class AccountSourceOrigin(StrEnum):
    """`account_source.origin`."""

    MANUAL = "MANUAL"
    DETECTED = "DETECTED"


class AccountSourceStatus(StrEnum):
    """`account_source.status`."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ContactPersona(StrEnum):
    """`contact.persona` (the Persona values table)."""

    CIO = "CIO"
    CTO = "CTO"
    COO = "COO"
    CFO = "CFO"
    CISO = "CISO"
    HEAD_OF_DIGITAL_TRANSFORMATION = "HEAD_OF_DIGITAL_TRANSFORMATION"
    HEAD_OF_AUTOMATION = "HEAD_OF_AUTOMATION"
    HEAD_OF_PROCESS_EXCELLENCE = "HEAD_OF_PROCESS_EXCELLENCE"
    HEAD_OF_SHARED_SERVICES = "HEAD_OF_SHARED_SERVICES"
    OTHER = "OTHER"


class ContactPersonaOrigin(StrEnum):
    """`contact.persona_origin`."""

    MANUAL = "MANUAL"
    CLASSIFIER = "CLASSIFIER"


class DiscoveryCandidateOrigin(StrEnum):
    """`discovery_candidate.origin`."""

    CRUNCHBASE_SEARCH = "CRUNCHBASE_SEARCH"
    NEWS_MENTION = "NEWS_MENTION"


class DiscoveryCandidateStatus(StrEnum):
    """`discovery_candidate.status`."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class SourcePluginCode(StrEnum):
    """`source_plugin.code`; reused by `plugin_usage.plugin_code` and `document.plugin_code`."""

    GDELT = "GDELT"
    RSS = "RSS"
    WEBSITE = "WEBSITE"
    CAREERS = "CAREERS"
    CRUNCHBASE = "CRUNCHBASE"
    NEWSAPI = "NEWSAPI"
    SERPAPI = "SERPAPI"


class PipelineRunKind(StrEnum):
    """`pipeline_run.kind`."""

    ACCOUNT_REFRESH = "ACCOUNT_REFRESH"
    RECLASSIFY = "RECLASSIFY"
    RESCORE = "RESCORE"
    DISCOVERY = "DISCOVERY"
    EVALUATION = "EVALUATION"


class PipelineRunTrigger(StrEnum):
    """`pipeline_run.trigger`."""

    SCHEDULE = "SCHEDULE"
    USER = "USER"
    QUESTION_CHANGE = "QUESTION_CHANGE"
    SCORING_ACTIVATION = "SCORING_ACTIVATION"
    ACCOUNT_CHANGE = "ACCOUNT_CHANGE"
    FEEDBACK = "FEEDBACK"
    OVERRIDE = "OVERRIDE"


class PipelineRunStatus(StrEnum):
    """`pipeline_run.status`."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineRunStage(StrEnum):
    """`pipeline_run.stage`."""

    FETCH = "FETCH"
    PROCESS = "PROCESS"
    TRIAGE = "TRIAGE"
    CLASSIFY = "CLASSIFY"
    EVIDENCE = "EVIDENCE"
    SCORE = "SCORE"


class JobStep(StrEnum):
    """`job.step`."""

    FETCH = "FETCH"
    PROCESS = "PROCESS"
    SIGNAL = "SIGNAL"
    SCORE = "SCORE"
    DISCOVER = "DISCOVER"
    EVALUATE = "EVALUATE"


class JobStatus(StrEnum):
    """`job.status`."""

    READY = "READY"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DocumentSourceType(StrEnum):
    """`document.source_type`."""

    NEWS = "NEWS"
    COMPANY_PUBLICATION = "COMPANY_PUBLICATION"
    JOB_POSTING = "JOB_POSTING"
    COMPANY_PROFILE = "COMPANY_PROFILE"


class DocumentTriageClassifier(StrEnum):
    """`document_triage.classifier`; reused by `classification.classifier` and
    `evaluation_result.classifier`."""

    JEV = "JEV"
    LLM = "LLM"


class DocumentTriageOutcome(StrEnum):
    """`document_triage.outcome`."""

    KEPT = "KEPT"
    NOT_ABOUT_ACCOUNT = "NOT_ABOUT_ACCOUNT"
    IRRELEVANT = "IRRELEVANT"


class ClassificationStatus(StrEnum):
    """`classification.status`."""

    NEGATIVE = "NEGATIVE"
    POSITIVE = "POSITIVE"
    PENDING_LLM = "PENDING_LLM"
    EVIDENCE_FAILED = "EVIDENCE_FAILED"


class FindingStrength(StrEnum):
    """`finding.strength`; reused by `classification.strength` and
    `evaluation_item.expected_strength`."""

    NONE = "NONE"
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


class FindingDecidedBy(StrEnum):
    """`finding.decided_by`."""

    CLASSIFIER = "CLASSIFIER"
    LLM = "LLM"


class FindingStatus(StrEnum):
    """`finding.status`."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class AccountScoreStanding(StrEnum):
    """`account_score.standing`."""

    RANKED = "RANKED"
    BELOW_FIT = "BELOW_FIT"
    DISQUALIFIED = "DISQUALIFIED"
    CUSTOMER = "CUSTOMER"


class AccountScoreBand(StrEnum):
    """`account_score.band`."""

    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class DisqualifierOverrideStatus(StrEnum):
    """`disqualifier_override.status`."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class AlertKind(StrEnum):
    """`alert.kind`."""

    STRONG_SIGNAL = "STRONG_SIGNAL"
    BAND_UP = "BAND_UP"


class LeadFeedbackVerdict(StrEnum):
    """`lead_feedback.verdict`."""

    RELEVANT = "RELEVANT"
    NOT_RELEVANT = "NOT_RELEVANT"
    ALREADY_CUSTOMER = "ALREADY_CUSTOMER"


class FindingFeedbackVerdict(StrEnum):
    """`finding_feedback.verdict`."""

    CORRECT = "CORRECT"
    WRONG = "WRONG"


class EvaluationItemOrigin(StrEnum):
    """`evaluation_item.origin`."""

    MANUAL = "MANUAL"
    FINDING_FEEDBACK = "FINDING_FEEDBACK"


class EvaluationItemStatus(StrEnum):
    """`evaluation_item.status`."""

    ACTIVE = "ACTIVE"
    STALE = "STALE"


class OutreachDraftChannel(StrEnum):
    """`outreach_draft.channel`."""

    EMAIL = "EMAIL"
    LINKEDIN_INMAIL = "LINKEDIN_INMAIL"


class OutreachDraftStatus(StrEnum):
    """`outreach_draft.status`."""

    DRAFT = "DRAFT"
    EXPORTED = "EXPORTED"


class CrmSyncTarget(StrEnum):
    """`crm_sync.target`."""

    HUBSPOT = "HUBSPOT"


class CrmSyncStatus(StrEnum):
    """`crm_sync.status`."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AuditEventKind(StrEnum):
    """`audit_event.kind`."""

    AUTH = "AUTH"
    USER = "USER"
    CONFIG = "CONFIG"
    ACCOUNT = "ACCOUNT"
    CONTACT = "CONTACT"
    RUN = "RUN"
    OVERRIDE = "OVERRIDE"
    FEEDBACK = "FEEDBACK"
    OUTREACH = "OUTREACH"
    CRM = "CRM"
    AI_CALL = "AI_CALL"
