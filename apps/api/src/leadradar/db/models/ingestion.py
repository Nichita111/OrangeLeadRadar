"""[Ingestion](/architecture/sql-store.md#ingestion): `source_plugin`, `plugin_usage`,
`pipeline_run`, `job`, `document`, `chunk`."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Index, SmallInteger, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from leadradar.api.settings import ApiSettings
from leadradar.core.enums import (
    DocumentSourceType,
    JobStatus,
    JobStep,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    PipelineRunTrigger,
    SourcePluginCode,
)
from leadradar.db.base import TimestampedBase
from leadradar.db.types import fk_uuid, pg_enum

# `chunk.embedding` is frozen at the dimension in force when the first migration runs
# (see The first migration, [design](/.work/stack-foundation/design.md)); the model uses the
# same configuration default so the two never drift silently.
EMBEDDING_DIM: int = ApiSettings.model_fields["embedding_dim"].default


class SourcePlugin(TimestampedBase):
    """[`source_plugin`](/architecture/sql-store.md#source_plugin)."""

    __tablename__ = "source_plugin"

    code: Mapped[SourcePluginCode] = mapped_column(
        pg_enum(SourcePluginCode, "source_plugin_code"), unique=True
    )
    enabled: Mapped[bool]
    rate_limit_per_minute: Mapped[int]
    daily_quota: Mapped[int | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None]
    last_error_at: Mapped[datetime | None]


class PluginUsage(TimestampedBase):
    """[`plugin_usage`](/architecture/sql-store.md#plugin_usage)."""

    __tablename__ = "plugin_usage"

    plugin_code: Mapped[SourcePluginCode] = mapped_column(
        pg_enum(SourcePluginCode, "source_plugin_code")
    )
    day: Mapped[date]
    requests: Mapped[int]

    __table_args__ = (UniqueConstraint("plugin_code", "day"),)


class PipelineRun(TimestampedBase):
    """[`pipeline_run`](/architecture/sql-store.md#pipeline_run)."""

    __tablename__ = "pipeline_run"

    kind: Mapped[PipelineRunKind] = mapped_column(pg_enum(PipelineRunKind, "pipeline_run_kind"))
    trigger: Mapped[PipelineRunTrigger] = mapped_column(
        pg_enum(PipelineRunTrigger, "pipeline_run_trigger")
    )
    account_id: Mapped[uuid.UUID | None] = fk_uuid("account.id", nullable=True)
    service_id: Mapped[uuid.UUID | None] = fk_uuid("service.id", nullable=True)
    question_id: Mapped[uuid.UUID | None] = fk_uuid("signal_question.id", nullable=True)
    status: Mapped[PipelineRunStatus] = mapped_column(
        pg_enum(PipelineRunStatus, "pipeline_run_status")
    )
    stage: Mapped[PipelineRunStage | None] = mapped_column(
        pg_enum(PipelineRunStage, "pipeline_run_stage"), nullable=True
    )
    progress: Mapped[dict[str, object]] = mapped_column(JSONB)
    errors: Mapped[list[object]] = mapped_column(JSONB)
    requested_by: Mapped[uuid.UUID | None] = fk_uuid("app_user.id", nullable=True)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        Index(
            "uq_pipeline_run_account_refresh_active",
            "account_id",
            unique=True,
            postgresql_where=text("kind = 'ACCOUNT_REFRESH' AND status IN ('QUEUED', 'RUNNING')"),
        ),
        Index(
            "uq_pipeline_run_discovery_active",
            "service_id",
            unique=True,
            postgresql_where=text("kind = 'DISCOVERY' AND status IN ('QUEUED', 'RUNNING')"),
        ),
    )


class Job(TimestampedBase):
    """[`job`](/architecture/sql-store.md#job)."""

    __tablename__ = "job"

    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id")
    step: Mapped[JobStep] = mapped_column(pg_enum(JobStep, "job_step"))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(pg_enum(JobStatus, "job_status"))
    priority: Mapped[int] = mapped_column(SmallInteger)
    attempts: Mapped[int]
    not_before: Mapped[datetime]
    locked_by: Mapped[str | None]
    locked_at: Mapped[datetime | None]
    last_error: Mapped[str | None]

    __table_args__ = (Index("ix_job_claiming", "status", "priority", "not_before"),)


class Document(TimestampedBase):
    """[`document`](/architecture/sql-store.md#document)."""

    __tablename__ = "document"

    account_id: Mapped[uuid.UUID | None] = fk_uuid("account.id", nullable=True)
    run_id: Mapped[uuid.UUID] = fk_uuid("pipeline_run.id")
    plugin_code: Mapped[SourcePluginCode] = mapped_column(
        pg_enum(SourcePluginCode, "source_plugin_code")
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(
        pg_enum(DocumentSourceType, "document_source_type")
    )
    url: Mapped[str]
    canonical_url: Mapped[str]
    title: Mapped[str | None]
    language: Mapped[str]
    published_at: Mapped[datetime | None]
    fetched_at: Mapped[datetime]
    content_hash: Mapped[str]
    text: Mapped[str | None]
    duplicate_of_id: Mapped[uuid.UUID | None] = fk_uuid("document.id", nullable=True)
    purge_after: Mapped[date]
    purged_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("account_id", "content_hash", postgresql_nulls_not_distinct=True),
    )


class Chunk(TimestampedBase):
    """[`chunk`](/architecture/sql-store.md#chunk)."""

    __tablename__ = "chunk"

    document_id: Mapped[uuid.UUID] = fk_uuid("document.id")
    ordinal: Mapped[int]
    char_start: Mapped[int]
    char_end: Mapped[int]
    section: Mapped[str | None]
    text: Mapped[str | None]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    lexemes: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        Index(
            "ix_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunk_lexemes_gin", "lexemes", postgresql_using="gin"),
    )
