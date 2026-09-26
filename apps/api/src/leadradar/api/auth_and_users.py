"""Router of the [Authentication and users](/architecture/interfaces.md#authentication-and-users)
family: `API-01` to `API-06`, `API-78`. Every route is a declared stub answering
`501 NOT_IMPLEMENTED` ([api Design](/architecture/services/api.md#design), "Declared contracts");
task 2 implements `API-01` to `API-03`, `API-78`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.router_utils import stub_router
from leadradar.core.enums import AppUserRole, AppUserStatus

router = stub_router("auth-and-users")


class LoginRequest(BaseModel):
    """[`LoginRequest`](/architecture/interfaces.md#loginrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str
    password: str


class DemoLoginRequest(BaseModel):
    """[`DemoLoginRequest`](/architecture/interfaces.md#demologinrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: AppUserRole


class AuthenticatedUser(BaseModel):
    """[`AuthenticatedUser`](/architecture/interfaces.md#authenticateduser)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    email: str
    display_name: str
    role: AppUserRole


class User(BaseModel):
    """[`User`](/architecture/interfaces.md#user)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    email: str
    display_name: str
    role: AppUserRole
    status: AppUserStatus
    last_login_at: str | None


class UserCreate(BaseModel):
    """[`UserCreate`](/architecture/interfaces.md#usercreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str
    display_name: str
    role: AppUserRole
    password: str


class UserUpdate(BaseModel):
    """[`UserUpdate`](/architecture/interfaces.md#userupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str | None = None
    role: AppUserRole | None = None
    status: AppUserStatus | None = None
    password: str | None = None


@router.post("/auth/login", response_model=AuthenticatedUser)
async def login(payload: LoginRequest) -> AuthenticatedUser:
    """`API-01`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/auth/logout", status_code=204)
async def logout() -> None:
    """`API-02`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/auth/me", response_model=AuthenticatedUser)
async def get_current_user() -> AuthenticatedUser:
    """`API-03`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/users", response_model=list[User])
async def list_users() -> list[User]:
    """`API-04`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/users", response_model=User)
async def create_user(payload: UserCreate) -> User:
    """`API-05`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.patch("/users/{id}", response_model=User)
async def update_user(id: str, payload: UserUpdate) -> User:
    """`API-06`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/auth/demo-login", response_model=AuthenticatedUser)
async def demo_login(payload: DemoLoginRequest) -> AuthenticatedUser:
    """`API-78`."""
    raise AssertionError("unreachable: contract_not_built already raised")
