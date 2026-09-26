"""Router of the [Industries and markets](/architecture/interfaces.md#industries-and-markets)
family: `API-71` to `API-76`. Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import IndustryStatus, MarketStatus

router = stub_router("industries-and-markets")


class Industry(BaseModel):
    """[`Industry`](/architecture/interfaces.md#industry)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    label: str
    status: IndustryStatus
    account_count: int


class IndustryCreate(BaseModel):
    """[`IndustryCreate`](/architecture/interfaces.md#industrycreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    label: str


class IndustryUpdate(BaseModel):
    """[`IndustryUpdate`](/architecture/interfaces.md#industryupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = None
    status: IndustryStatus | None = None


class Market(BaseModel):
    """[`Market`](/architecture/interfaces.md#market)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str
    country_codes: list[str]
    status: MarketStatus


class MarketCreate(BaseModel):
    """[`MarketCreate`](/architecture/interfaces.md#marketcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str
    country_codes: list[str]


class MarketUpdate(BaseModel):
    """[`MarketUpdate`](/architecture/interfaces.md#marketupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = None
    country_codes: list[str] | None = None
    status: MarketStatus | None = None


@router.get("/industries", response_model=list[Industry])
async def list_industries(status: IndustryStatus | None = None) -> list[Industry]:
    """`API-71`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/industries", response_model=Industry)
async def create_industry(payload: IndustryCreate) -> Industry:
    """`API-72`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/industries/{code}", response_model=Industry)
async def update_industry(code: str, payload: IndustryUpdate) -> Industry:
    """`API-73`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/markets", response_model=list[Market])
async def list_markets(status: MarketStatus | None = None) -> list[Market]:
    """`API-74`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/markets", response_model=Market)
async def create_market(payload: MarketCreate) -> Market:
    """`API-75`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/markets/{code}", response_model=Market)
async def update_market(code: str, payload: MarketUpdate) -> Market:
    """`API-76`."""
    raise AssertionError("unreachable: contract_not_built already raised")
