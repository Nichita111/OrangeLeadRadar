"""The [Embedder](/architecture/interfaces.md#embedder) port (`API-67`): `POST {EMBEDDER_URL}/embed`
against the Text Embeddings Inference container. The local embedder runs live in every mode
([ADR-11](/architecture/adrs/adr-11-recorded-fixtures.md)), so this client never goes through the
record/replay transport of [`fixtures`](fixtures.md)."""

from __future__ import annotations

import httpx

from leadradar.ai.errors import UpstreamUnavailable


def build_embedder_client(timeout_s: float = 30.0) -> httpx.AsyncClient:
    """A plain client: the embedder is local and always live, in every `FIXTURE_MODE`."""
    return httpx.AsyncClient(timeout=timeout_s)


def _is_finite_vector(vector: object, dim: int) -> bool:
    return (
        isinstance(vector, list)
        and len(vector) == dim
        and all(isinstance(value, int | float) and value == value for value in vector)  # not NaN
    )


async def embed(
    http: httpx.AsyncClient, *, embedder_url: str, dim: int, batch_size: int, texts: list[str]
) -> list[list[float]]:
    """`API-67`: one vector per text, at most `batch_size` per call. Raises `UpstreamUnavailable`
    (`dependency="embedder"`) on a transport error or a response that is not exactly one vector
    of `dim` finite numbers per text."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            response = await http.post(f"{embedder_url}/embed", json={"inputs": batch})
        except httpx.TransportError as error:
            raise UpstreamUnavailable("embedder", "ERROR", str(error)) from error
        if not response.is_success:
            raise UpstreamUnavailable(
                "embedder", "ERROR", f"embedder answered {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise UpstreamUnavailable("embedder", "INVALID_OUTPUT", "not JSON") from error
        if not isinstance(payload, list) or len(payload) != len(batch):
            raise UpstreamUnavailable("embedder", "INVALID_OUTPUT", "not one vector per text")
        for vector in payload:
            if not _is_finite_vector(vector, dim):
                raise UpstreamUnavailable("embedder", "INVALID_OUTPUT", f"not {dim} finite numbers")
            vectors.append([float(value) for value in vector])
    return vectors
