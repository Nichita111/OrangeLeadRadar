"""Router of the [Authentication and users](/architecture/interfaces.md#authentication-and-users)
family: `API-01` to `API-06`. Each route validates its input into a Pydantic model, calls one
`auth` capability function, and shapes the response (api Design "Layering")."""

from __future__ import annotations

import http.cookies
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import (
    SESSION_COOKIE_NAME,
    current_user,
    require_admin,
)
from leadradar.api.constants import API_PREFIX
from leadradar.auth.sessions import sign_in, sign_out
from leadradar.auth.users import (
    UserCreateData,
    UserUpdateData,
    create_user,
    list_users,
    update_user,
)
from leadradar.core.enums import AppUserRole, AppUserStatus
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from leadradar.settings import ApiSettings


class LoginRequest(BaseModel):
    """[`LoginRequest`](/architecture/interfaces.md#loginrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str
    password: SecretStr


class AuthenticatedUser(BaseModel):
    """[`AuthenticatedUser`](/architecture/interfaces.md#authenticateduser)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: AppUserRole


class User(BaseModel):
    """[`User`](/architecture/interfaces.md#user)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: AppUserRole
    status: AppUserStatus
    last_login_at: datetime | None


class UserCreate(BaseModel):
    """[`UserCreate`](/architecture/interfaces.md#usercreate). `password`'s `PASSWORD_MIN_LENGTH`
    is enforced once, by `auth.users.create_user` (its one owner), not a static `Field`
    constraint: the minimum is a runtime setting, and a model built inside a router factory
    cannot be resolved by FastAPI's OpenAPI generation (`from __future__ import annotations`
    turns the route's own annotation into a forward reference that must be a module-level
    name)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str
    display_name: str
    role: AppUserRole
    password: SecretStr


class UserUpdate(BaseModel):
    """[`UserUpdate`](/architecture/interfaces.md#userupdate). `password`'s `PASSWORD_MIN_LENGTH`
    is enforced once, by `auth.users.update_user` (`UserCreate`'s note)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str | None = None
    role: AppUserRole | None = None
    status: AppUserStatus | None = None
    password: SecretStr | None = None


def _to_authenticated_user(user: AppUser) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id, email=user.email, display_name=user.display_name, role=user.role
    )


def _to_user(user: AppUser) -> User:
    return User(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        last_login_at=user.last_login_at,
    )


# [Conventions](/architecture/interfaces.md#conventions) Authentication and G6 require the
# attribute spelled exactly `SameSite=Lax`; `Response.set_cookie`'s `samesite` parameter always
# lower-cases the value it stores in the `Set-Cookie` header, so the cookie is built directly
# with `http.cookies.SimpleCookie` instead (the same mechanism `set_cookie` itself uses).
def _session_cookie_header(*, value: str, max_age: int) -> str:
    cookie: http.cookies.BaseCookie[str] = http.cookies.SimpleCookie()
    cookie[SESSION_COOKIE_NAME] = value
    cookie[SESSION_COOKIE_NAME]["max-age"] = max_age
    cookie[SESSION_COOKIE_NAME]["path"] = API_PREFIX
    cookie[SESSION_COOKIE_NAME]["httponly"] = True
    cookie[SESSION_COOKIE_NAME]["secure"] = True
    cookie[SESSION_COOKIE_NAME]["samesite"] = "Lax"
    return cookie.output(header="").strip()


def _set_session_cookie(response: Response, token: bytes, settings: ApiSettings) -> None:
    header = _session_cookie_header(value=token.hex(), max_age=settings.session_ttl_hours * 3600)
    response.raw_headers.append((b"set-cookie", header.encode("latin-1")))


def _clear_session_cookie(response: Response) -> None:
    header = _session_cookie_header(value="", max_age=0)
    response.raw_headers.append((b"set-cookie", header.encode("latin-1")))


def build_auth_router(settings: ApiSettings) -> APIRouter:
    """`API-01` to `API-03`, anonymous or any signed-in user."""
    router = APIRouter(tags=["authentication-and-users"])

    @router.post("/auth/login", response_model=AuthenticatedUser)
    async def login(
        payload: LoginRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(get_session),
    ) -> AuthenticatedUser:
        token = secrets.token_bytes(32)
        user = await sign_in(
            db,
            email=payload.email,
            password=payload.password.get_secret_value(),
            now=request.app.state.clock(),
            token=token,
            max_failures=settings.login_max_failures,
            lock_minutes=settings.login_lock_minutes,
            session_ttl_hours=settings.session_ttl_hours,
        )
        _set_session_cookie(response, token, settings)
        return _to_authenticated_user(user)

    @router.post("/auth/logout", status_code=204)
    async def logout(
        request: Request,
        response: Response,
        user: AppUser = Depends(current_user),
        db: AsyncSession = Depends(get_session),
        session_cookie: str = Cookie(alias=SESSION_COOKIE_NAME),
    ) -> None:
        # `session_cookie` is guaranteed present: `current_user` above already required and
        # validated it, raising `Unauthenticated` before this body runs otherwise.
        await sign_out(
            db,
            actor_id=user.id,
            token=bytes.fromhex(session_cookie),
            now=request.app.state.clock(),
        )
        _clear_session_cookie(response)

    @router.get("/auth/me", response_model=AuthenticatedUser)
    async def me(user: AppUser = Depends(current_user)) -> AuthenticatedUser:
        return _to_authenticated_user(user)

    return router


def build_users_router(settings: ApiSettings) -> APIRouter:
    """`API-04` to `API-06`, Admin only ([Conventions](
    /architecture/interfaces.md#conventions) Roles)."""
    router = APIRouter(tags=["authentication-and-users"], dependencies=[Depends(require_admin)])

    @router.get("/users", response_model=list[User])
    async def get_users(db: AsyncSession = Depends(get_session)) -> list[User]:
        users = await list_users(db)
        return [_to_user(user) for user in users]

    @router.post("/users", response_model=User, status_code=200)
    async def create_user_route(
        payload: UserCreate,
        request: Request,
        admin: AppUser = Depends(require_admin),
        db: AsyncSession = Depends(get_session),
    ) -> User:
        data = UserCreateData(
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            password=payload.password.get_secret_value(),
        )
        user = await create_user(
            db,
            actor_id=admin.id,
            data=data,
            now=request.app.state.clock(),
            password_min_length=settings.password_min_length,
        )
        return _to_user(user)

    @router.patch("/users/{user_id}", response_model=User)
    async def update_user_route(
        user_id: uuid.UUID,
        payload: UserUpdate,
        request: Request,
        admin: AppUser = Depends(require_admin),
        db: AsyncSession = Depends(get_session),
    ) -> User:
        data = UserUpdateData(
            display_name=payload.display_name,
            role=payload.role,
            status=payload.status,
            password=(
                payload.password.get_secret_value() if payload.password is not None else None
            ),
        )
        user = await update_user(
            db,
            actor_id=admin.id,
            user_id=user_id,
            data=data,
            now=request.app.state.clock(),
            password_min_length=settings.password_min_length,
        )
        return _to_user(user)

    return router
