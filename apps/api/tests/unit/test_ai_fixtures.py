"""Unit tests of record and replay ([Fixture files](/architecture/overview.md#runtime),
[S-RUN-02](/requirements/system.md)): a recorded exchange replays identically without a live
transport, a missing recording raises `FixtureMissing` and sends nothing, and neither the key nor
the file carries a header."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from leadradar.ai.fixtures import (
    ADAPTER_EXTENSION,
    FixtureMissing,
    build_fixture_client,
    fixture_key,
    normalise_request,
)
from leadradar.ai.settings import FixtureMode

pytestmark = pytest.mark.unit

URL = "https://example.test/api/v1/chat/completions"
BODY = {"model": "m", "messages": [{"role": "user", "content": "Grüße"}]}
EXTENSIONS = {ADAPTER_EXTENSION: "OPENROUTER"}


def _live(response: httpx.Response, sent: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    return httpx.MockTransport(handler)


async def _post(client: httpx.AsyncClient) -> httpx.Response:
    async with client:
        return await client.post(
            URL, json=BODY, headers={"Authorization": "Bearer secret-key"}, extensions=EXTENSIONS
        )


async def test_a_recorded_exchange_replays_without_a_live_call(tmp_path: Path) -> None:
    sent: list[httpx.Request] = []
    live = _live(httpx.Response(200, json={"answer": "ok", "n": 1}), sent)

    recorded = await _post(build_fixture_client("record", tmp_path, live))
    replayed = await _post(build_fixture_client("replay", tmp_path, live))

    assert len(sent) == 1
    assert replayed.status_code == recorded.status_code == 200
    assert replayed.json() == recorded.json() == {"answer": "ok", "n": 1}


async def test_the_file_holds_the_normalised_request_and_no_header(tmp_path: Path) -> None:
    live = _live(httpx.Response(200, json={"answer": "ok"}), [])

    await _post(build_fixture_client("record", tmp_path, live))

    [path] = list((tmp_path / "OPENROUTER").glob("*.json"))
    text = path.read_text()
    assert "secret-key" not in text
    document = json.loads(text)
    assert document["adapter"] == "OPENROUTER"
    assert document["request"] == {
        "adapter": "OPENROUTER",
        "method": "POST",
        "url": URL,
        "body": BODY,
    }
    assert document["response"]["status"] == 200
    assert document["response"]["json"] == {"answer": "ok"}
    expected_key = fixture_key(
        normalise_request(
            "OPENROUTER", httpx.Request("POST", URL, json=BODY, extensions=EXTENSIONS)
        )
    )
    assert path.name == f"{expected_key}.json"


async def test_a_missing_recording_fails_and_nothing_is_sent(tmp_path: Path) -> None:
    sent: list[httpx.Request] = []
    live = _live(httpx.Response(200, json={}), sent)

    with pytest.raises(FixtureMissing) as excinfo:
        await _post(build_fixture_client("replay", tmp_path, live))

    assert excinfo.value.adapter == "OPENROUTER"
    assert sent == []


def test_the_key_ignores_headers_and_the_order_of_query_parameters() -> None:
    first = httpx.Request("GET", "https://example.test/a?b=2&a=1", headers={"X-A": "1"})
    second = httpx.Request("GET", "https://example.test/a?a=1&b=2")

    assert fixture_key(normalise_request("GDELT", first)) == fixture_key(
        normalise_request("GDELT", second)
    )
    assert fixture_key(normalise_request("GDELT", first)) != fixture_key(
        normalise_request("RSS", first)
    )


async def test_a_recorded_timeout_replays_as_a_timeout(tmp_path: Path) -> None:
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(httpx.ReadTimeout):
        await _post(build_fixture_client("record", tmp_path, httpx.MockTransport(time_out)))

    with pytest.raises(httpx.TimeoutException):
        await _post(build_fixture_client("replay", tmp_path))


async def test_binary_and_text_bodies_replay_byte_for_byte(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7\n\xff\xfe\x00binary"
    responses = {
        "/report.pdf": httpx.Response(
            200, headers={"content-type": "application/pdf"}, content=pdf
        ),
        "/page.html": httpx.Response(
            200, headers={"content-type": "text/html"}, text="<p>Hallo</p>"
        ),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return responses[request.url.path]

    extensions = {ADAPTER_EXTENSION: "WEBSITE"}
    modes: tuple[FixtureMode, ...] = ("record", "replay")
    for mode in modes:
        async with build_fixture_client(mode, tmp_path, httpx.MockTransport(handler)) as client:
            pdf_response = await client.get(
                "https://example.test/report.pdf", extensions=extensions
            )
            html_response = await client.get(
                "https://example.test/page.html", extensions=extensions
            )
        assert pdf_response.content == pdf
        assert html_response.text == "<p>Hallo</p>"
