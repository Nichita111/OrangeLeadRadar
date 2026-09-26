"""Router of the [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
family, its contacts half: `API-25` to `API-28`. The accounts half (`API-20` to `API-24`) is
built in `leadradar.api.accounts`. Every route here is a declared stub answering
`501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import ContactPersona, ContactPersonaOrigin

router = stub_router("accounts-and-contacts")


class Contact(BaseModel):
    """[`Contact`](/architecture/interfaces.md#contact)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    account_id: str
    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona
    persona_origin: ContactPersonaOrigin
    retain_until: str


class ContactCreate(BaseModel):
    """[`ContactCreate`](/architecture/interfaces.md#contactcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona | SkipJsonSchema[None] = None


class ContactUpdate(BaseModel):
    """[`ContactUpdate`](/architecture/interfaces.md#contactupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str | SkipJsonSchema[None] = None
    job_title: str | SkipJsonSchema[None] = None
    source_url: str | SkipJsonSchema[None] = None
    persona: ContactPersona | SkipJsonSchema[None] = None


@router.get("/accounts/{id}/contacts", response_model=list[Contact])
async def list_contacts(id: str) -> list[Contact]:
    """`API-25`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/accounts/{id}/contacts", response_model=Contact)
async def create_contact(id: str, payload: ContactCreate) -> Contact:
    """`API-26`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/contacts/{id}", response_model=Contact)
async def update_contact(id: str, payload: ContactUpdate) -> Contact:
    """`API-27`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.delete("/contacts/{id}", status_code=204)
async def delete_contact(id: str) -> None:
    """`API-28`."""
    raise AssertionError("unreachable: contract_not_built already raised")
