"""[`API-68`](/architecture/interfaces.md#source-plug-ins-contracts): the in-process port every
source plug-in adapter implements."""

from __future__ import annotations

from typing import Protocol

from leadradar.plugins.http import CrawlHttpClient
from leadradar.plugins.shapes import FetchContext, RawItem


class SourcePluginAdapter(Protocol):
    """`fetch(context)`: makes no request when unavailable (the caller only calls a plug-in it
    has already found available), never returns a partial list as if it were complete — a
    provider failure is raised, not swallowed into a short list."""

    async def fetch(self, context: FetchContext, client: CrawlHttpClient) -> list[RawItem]: ...
