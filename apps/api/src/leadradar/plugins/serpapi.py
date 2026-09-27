"""The `SERPAPI` `search` adapter of `API-69`, engine `google`: used only by [Source
detection](/architecture/rules.md#source-detection)'s web-search half, one request per missing
`CAREERS` or `INVESTOR_RELATIONS` kind, answering with its organic results' links in order."""

from __future__ import annotations

from urllib.parse import urlencode

from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.http import CrawlHttpClient

_SEARCH_URL = "https://serpapi.com/search.json"


class SerpapiWebSearch:
    """`API-69` for `SERPAPI`: one `engine=google` web search."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, query: str, client: CrawlHttpClient) -> list[str]:
        """The `link` of each organic result, in order. `client.get` itself raises
        `PluginFetchFailed` on a transport error, `429` or `5xx`; a non-JSON answer raises it
        too, as the other search adapters do."""
        params = {"engine": "google", "q": query, "api_key": self._api_key}
        url = f"{_SEARCH_URL}?{urlencode(params)}"
        response = await client.get(url)
        try:
            payload = response.json()
        except ValueError as error:
            raise PluginFetchFailed(f"SERPAPI answered non-JSON for {query!r}") from error
        results = payload.get("organic_results") if isinstance(payload, dict) else None
        links: list[str] = []
        for result in results or []:
            link = result.get("link") if isinstance(result, dict) else None
            if isinstance(link, str):
                links.append(link)
        return links
