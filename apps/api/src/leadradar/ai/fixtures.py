"""Record and replay of every outbound exchange
([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)), as an `httpx` transport, in the
file format of [Fixture files](/architecture/overview.md#runtime).

`FixtureTransport` sits under the `httpx.AsyncClient` of the AI gateway (and of the source
plug-ins): in `replay` it answers from `FIXTURE_DIR` and never holds a live transport, so a
missing recording raises `FixtureMissing` and cannot fall back to a live call; in `record` it
forwards to the live transport and stores the exchange. Every request names its adapter in the
`fixture_adapter` request extension, since the adapter is part of the key."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from leadradar.ai.settings import FixtureMode

ADAPTER_EXTENSION = "fixture_adapter"

ReplayMode = Literal["record", "replay"]


class FixtureMissing(Exception):
    """`FIXTURE_MISSING`: replay found no recording for a request; nothing was sent."""

    def __init__(self, adapter: str, key: str) -> None:
        super().__init__(f"No recording for adapter {adapter} with key {key}")
        self.adapter = adapter
        self.key = key


@dataclass(frozen=True)
class FixtureRequest:
    """The normalised request: what the key is computed over and what the file stores."""

    adapter: str
    method: str
    url: str
    body: object

    def as_json(self) -> dict[str, object]:
        return {"adapter": self.adapter, "method": self.method, "url": self.url, "body": self.body}


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sorted_query_url(url: httpx.URL) -> str:
    parts = urlsplit(str(url))
    query = urlencode(sorted(url.params.multi_items()))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _is_json(content_type: str) -> bool:
    return content_type.split(";")[0].strip().lower().endswith("json")


def normalise_request(adapter: str, request: httpx.Request) -> FixtureRequest:
    """Method, URL with sorted query and body; headers never enter the key or the file."""
    content = request.content
    body: object
    if not content:
        body = None
    elif _is_json(request.headers.get("content-type", "")):
        body = json.loads(content)
    else:
        body = content.decode("utf-8")
    return FixtureRequest(
        adapter=adapter, method=request.method, url=_sorted_query_url(request.url), body=body
    )


def fixture_key(fixture_request: FixtureRequest) -> str:
    """SHA-256, lower-case hex, of the normalised request as canonical JSON."""
    return hashlib.sha256(_canonical_json(fixture_request.as_json()).encode("utf-8")).hexdigest()


def fixture_path(fixture_dir: Path, fixture_request: FixtureRequest) -> Path:
    """`FIXTURE_DIR/<adapter>/<key>.json`."""
    return fixture_dir / fixture_request.adapter / f"{fixture_key(fixture_request)}.json"


def _response_record(response: httpx.Response) -> dict[str, object]:
    content_type = response.headers.get("content-type", "")
    record: dict[str, object] = {"status": response.status_code, "content_type": content_type}
    if _is_json(content_type):
        record["json"] = json.loads(response.content)
    else:
        try:
            record["text"] = response.content.decode("utf-8")
        except UnicodeDecodeError:
            record["base64"] = base64.b64encode(response.content).decode("ascii")
    return record


def _replayed_response(record: dict[str, object], request: httpx.Request) -> httpx.Response:
    error = record.get("error")
    if error == "TIMEOUT":
        raise httpx.ReadTimeout("Recorded timeout", request=request)
    if error == "TRANSPORT_ERROR":
        raise httpx.ConnectError("Recorded transport error", request=request)
    status = record["status"]
    content_type = record["content_type"]
    if not isinstance(status, int) or not isinstance(content_type, str):
        raise ValueError("A recorded response needs an integer status and a content type")
    if "json" in record:
        content = json.dumps(record["json"], ensure_ascii=False).encode("utf-8")
    elif isinstance(record.get("text"), str):
        content = str(record["text"]).encode("utf-8")
    else:
        content = base64.b64decode(str(record["base64"]))
    return httpx.Response(
        status, headers={"content-type": content_type}, content=content, request=request
    )


def _write(path: Path, fixture_request: FixtureRequest, response: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "adapter": fixture_request.adapter,
        "request": fixture_request.as_json(),
        "response": response,
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


class FixtureTransport(httpx.AsyncBaseTransport):
    """Records to, or replays from, `fixture_dir`. `live` is required in `record` and must be
    absent in `replay`, so replay has nothing it could send."""

    def __init__(
        self, mode: ReplayMode, fixture_dir: Path, live: httpx.AsyncBaseTransport | None
    ) -> None:
        if (mode == "record") != (live is not None):
            raise ValueError("record needs a live transport and replay must not have one")
        self._mode = mode
        self._fixture_dir = fixture_dir
        self._live = live

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        adapter = request.extensions.get(ADAPTER_EXTENSION)
        if not isinstance(adapter, str):
            raise ValueError(f"A recorded request names its adapter in `{ADAPTER_EXTENSION}`")
        fixture_request = normalise_request(adapter, request)
        path = fixture_path(self._fixture_dir, fixture_request)
        if self._live is None:
            if not path.is_file():
                raise FixtureMissing(adapter, fixture_key(fixture_request))
            document = json.loads(path.read_text())
            return _replayed_response(document["response"], request)
        return await self._record(request, fixture_request, path, self._live)

    async def _record(
        self,
        request: httpx.Request,
        fixture_request: FixtureRequest,
        path: Path,
        live: httpx.AsyncBaseTransport,
    ) -> httpx.Response:
        try:
            response = await live.handle_async_request(request)
        except httpx.TimeoutException:
            _write(path, fixture_request, {"error": "TIMEOUT"})
            raise
        except httpx.TransportError:
            _write(path, fixture_request, {"error": "TRANSPORT_ERROR"})
            raise
        await response.aread()
        _write(path, fixture_request, _response_record(response))
        # `aread` has already decoded the body, so the encoding headers no longer describe it.
        headers = [
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        ]
        return httpx.Response(
            response.status_code, headers=headers, content=response.content, request=request
        )

    async def aclose(self) -> None:
        if self._live is not None:
            await self._live.aclose()


def build_fixture_client(
    fixture_mode: FixtureMode,
    fixture_dir: Path,
    live: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """An `httpx.AsyncClient` for `FIXTURE_MODE`: `off` sends over `live` (the network when
    None); `record` sends over it and stores each exchange; `replay` never sends, whatever
    `live` is."""
    if fixture_mode == "replay":
        return httpx.AsyncClient(transport=FixtureTransport("replay", fixture_dir, None))
    network = live if live is not None else httpx.AsyncHTTPTransport()
    if fixture_mode == "record":
        return httpx.AsyncClient(transport=FixtureTransport("record", fixture_dir, network))
    return httpx.AsyncClient(transport=network)
