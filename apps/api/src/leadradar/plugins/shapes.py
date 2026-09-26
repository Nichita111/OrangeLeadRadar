"""[Source plug-ins shapes](/architecture/interfaces.md#source-plug-ins-shapes):
`FetchContext` and `RawItem`, plain dataclasses at the port boundary."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from leadradar.core.enums import AccountSourceKind, DocumentSourceType, SourcePluginCode

ContentType = Literal["HTML", "PDF", "JSON"]


@dataclass(frozen=True)
class FetchAccount:
    """`FetchContext.account`."""

    id: str
    name: str
    domain: str
    aliases: Sequence[str]
    country_code: str | None
    crunchbase_id: str | None


@dataclass(frozen=True)
class FetchSource:
    """One entry of `FetchContext.sources`."""

    kind: AccountSourceKind
    url: str


@dataclass(frozen=True)
class FetchContext:
    """[`FetchContext`](/architecture/interfaces.md#fetchcontext): what a plug-in's `fetch` call
    is given."""

    account: FetchAccount
    sources: Sequence[FetchSource]
    since: datetime
    until: datetime
    queries: Sequence[str]
    max_items: int


@dataclass(frozen=True)
class RawItem:
    """[`RawItem`](/architecture/interfaces.md#rawitem): one fetched item, before [Document
    normalisation](/architecture/rules.md#document-normalisation)."""

    url: str
    title: str | None
    published_at: datetime | None
    content_type: ContentType
    body: bytes
    source_type: DocumentSourceType
    plugin_code: SourcePluginCode
