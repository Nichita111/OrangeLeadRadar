"""Unit tests of the [Embedder](/architecture/interfaces.md#embedder) port's error naming
(`API-67`): every failure raises `UpstreamUnavailable` naming `Dependency.EMBEDDER`."""

from __future__ import annotations

import httpx
import pytest

from leadradar.ai.embedder import embed
from leadradar.ai.errors import UpstreamUnavailable
from leadradar.core.enums import Dependency

pytestmark = pytest.mark.unit


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_a_transport_error_names_the_embedder() -> None:
    def raise_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with _client(httpx.MockTransport(raise_error)) as http:
        with pytest.raises(UpstreamUnavailable) as excinfo:
            await embed(http, embedder_url="http://embedder", dim=3, batch_size=8, texts=["a"])
    assert excinfo.value.dependency == Dependency.EMBEDDER


async def test_a_non_success_status_names_the_embedder() -> None:
    async with _client(httpx.MockTransport(lambda request: httpx.Response(503))) as http:
        with pytest.raises(UpstreamUnavailable) as excinfo:
            await embed(http, embedder_url="http://embedder", dim=3, batch_size=8, texts=["a"])
    assert excinfo.value.dependency == Dependency.EMBEDDER


async def test_a_shape_mismatch_names_the_embedder() -> None:
    def wrong_shape(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[[0.1, 0.2]])

    async with _client(httpx.MockTransport(wrong_shape)) as http:
        with pytest.raises(UpstreamUnavailable) as excinfo:
            await embed(http, embedder_url="http://embedder", dim=3, batch_size=8, texts=["a"])
    assert excinfo.value.dependency == Dependency.EMBEDDER
