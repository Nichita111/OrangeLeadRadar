"""`make export-labels` and `make seed-labels` ([Seeding](/architecture/overview.md#runtime) after
D6, `S-RUN-03`): the labelled set exported to `FIXTURE_DIR/evaluation_items.json`, keyed by
account domain, document content hash, passage ordinal, service code and question key, and loaded
back onto a freshly refreshed demo dataset as `MANUAL` labels of the demo Admin (G9)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.clock import build_clock
from leadradar.core.enums import EvaluationItemStatus, FindingStrength
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.session import build_engine
from leadradar.evaluation.labels import label_pair
from leadradar.logs import configure_json_logging
from leadradar.seed.demo import DEMO_ADMIN_EMAIL
from leadradar.settings import ApiSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelEntry:
    """One row of `FIXTURE_DIR/evaluation_items.json`, the D6 format."""

    account_domain: str
    content_hash: str
    ordinal: int
    service_code: str
    question_key: str
    question_revision: int
    expected_strength: str

    def sort_key(self) -> tuple[str, str, int, str, str]:
        return (
            self.account_domain,
            self.content_hash,
            self.ordinal,
            self.service_code,
            self.question_key,
        )


# --- Export (`make export-labels`) -------------------------------------------------------------


async def export_entries(session: AsyncSession) -> list[LabelEntry]:
    """Every `ACTIVE` [`evaluation_item`](/architecture/sql-store.md#evaluation_item), as the D6
    entry, sorted by its key so a repeated export is byte-identical."""
    rows = (
        await session.execute(
            select(EvaluationItem, Chunk, Document, Account, SignalQuestion, Service)
            .join(Chunk, Chunk.id == EvaluationItem.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .join(Account, Account.id == Document.account_id)
            .join(SignalQuestion, SignalQuestion.id == EvaluationItem.question_id)
            .join(Service, Service.id == SignalQuestion.service_id)
            .where(EvaluationItem.status == EvaluationItemStatus.ACTIVE)
        )
    ).all()
    entries = [
        LabelEntry(
            account_domain=account.domain,
            content_hash=document.content_hash,
            ordinal=chunk.ordinal,
            service_code=service.code,
            question_key=question.key,
            question_revision=item.question_revision,
            expected_strength=item.expected_strength.value,
        )
        for item, chunk, document, account, question, service in rows
    ]
    return sorted(entries, key=LabelEntry.sort_key)


async def _run_export(settings: ApiSettings) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            entries = await export_entries(db)
    finally:
        await engine.dispose()
    json.dump([asdict(entry) for entry in entries], sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def export_run() -> None:
    """`leadradar-export-labels`: writes the D6 JSON array to stdout; `make export-labels`
    redirects it to `fixtures/evaluation_items.json` on the host, since `fixtures/` is read-only
    inside the container."""
    settings = ApiSettings()
    configure_json_logging(settings.log_level)
    asyncio.run(_run_export(settings))


# --- Load (`make seed-labels`) -----------------------------------------------------------------


class LabelEntriesUnmatched(Exception):
    """One or more entries of `FIXTURE_DIR/evaluation_items.json` matched no passage or question;
    nothing is written for any entry (D6: no partial success)."""

    def __init__(self, unmatched: list[str]) -> None:
        super().__init__(f"{len(unmatched)} label entries matched nothing: {', '.join(unmatched)}")
        self.unmatched = unmatched


async def _require_admin(db: AsyncSession) -> AppUser:
    return (await db.execute(select(AppUser).where(AppUser.email == DEMO_ADMIN_EMAIL))).scalar_one()


async def _resolve_chunk(db: AsyncSession, entry: LabelEntry) -> uuid.UUID | None:
    account_id = (
        await db.execute(select(Account.id).where(Account.domain == entry.account_domain))
    ).scalar_one_or_none()
    if account_id is None:
        return None
    document_id = (
        await db.execute(
            select(Document.id).where(
                Document.account_id == account_id, Document.content_hash == entry.content_hash
            )
        )
    ).scalar_one_or_none()
    if document_id is None:
        return None
    return (
        await db.execute(
            select(Chunk.id).where(Chunk.document_id == document_id, Chunk.ordinal == entry.ordinal)
        )
    ).scalar_one_or_none()


async def _resolve_question(db: AsyncSession, entry: LabelEntry) -> uuid.UUID | None:
    return (
        await db.execute(
            select(SignalQuestion.id)
            .join(Service, Service.id == SignalQuestion.service_id)
            .where(Service.code == entry.service_code, SignalQuestion.key == entry.question_key)
        )
    ).scalar_one_or_none()


async def load_entries(db: AsyncSession, entries: list[LabelEntry], *, now: datetime) -> None:
    """Resolves and writes every entry as a `MANUAL` label of the demo Admin (G9), the way
    `leadradar-refresh-demo` finds its Admin. Raises `LabelEntriesUnmatched` naming every entry
    that matched no passage or question, writing nothing (D6). Idempotent: a second load rewrites
    the same values, through `evaluation.labels.label_pair`'s own update-in-place."""
    admin = await _require_admin(db)
    resolved: list[tuple[LabelEntry, uuid.UUID, uuid.UUID]] = []
    unmatched: list[str] = []
    for entry in entries:
        chunk_id = await _resolve_chunk(db, entry)
        question_id = await _resolve_question(db, entry)
        if chunk_id is None or question_id is None:
            unmatched.append(json.dumps(asdict(entry), sort_keys=True))
            continue
        resolved.append((entry, chunk_id, question_id))
    if unmatched:
        raise LabelEntriesUnmatched(unmatched)

    for entry, chunk_id, question_id in resolved:
        await label_pair(
            db,
            principal=admin,
            chunk_id=chunk_id,
            question_id=question_id,
            question_revision=entry.question_revision,
            expected_strength=FindingStrength(entry.expected_strength),
            now=now,
        )


async def _run_load(settings: ApiSettings) -> None:
    path = settings.fixture_dir / "evaluation_items.json"
    if not path.is_file():
        raise FileNotFoundError(f"No label file at {path}.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = [LabelEntry(**row) for row in raw]

    engine = build_engine(settings.database_url.get_secret_value())
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            now = build_clock(settings)()
            await load_entries(db, entries, now=now)
    finally:
        await engine.dispose()


def run() -> None:
    """`leadradar-seed-labels`: fails loudly, listing every unmatched entry, rather than loading a
    partial labelled set."""
    settings = ApiSettings()
    configure_json_logging(settings.log_level)
    try:
        asyncio.run(_run_load(settings))
    except Exception:
        logger.exception("Loading the labelled set failed")
        sys.exit(1)
    logger.info("Loaded the labelled set")


if __name__ == "__main__":
    run()
