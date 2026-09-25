---
type: Feature
title: Identity and access
description: How users sign in and out with local accounts, how sessions and lockout work, how the Sales and Admin roles are enforced, and how an Admin manages users.
status: draft
tags: [identity-and-access]
---

# Identity and access

## Purpose

LeadRadar serves one organisation with two roles. Sales works accounts, prospects, feedback, labels and outreach; Admin also configures services, scoring, source plug-ins and users, adds exceptions, runs quality checks and reads the audit. Users sign in with an email address and password; the api enforces every role on every route.

## Flows

### FL-19 Sign in and sign out

1. An anonymous visitor is sent to [Sign in](#sign-in) with the page they wanted as return path.
2. Correct credentials set the session cookie (`API-01`) and return the user to that page; wrong ones answer one message that does not reveal which was wrong; `LOGIN_MAX_FAILURES` failures in a row lock the account for `LOGIN_LOCK_MINUTES`.
3. Sign out revokes the session (`API-02`). A session ends by itself after `SESSION_TTL_HOURS`.

### FL-20 Manage users

1. An Admin opens [Users](#users) and creates a user with email, display name, role and an initial password (`API-05`).
2. The Admin changes a user's role, disables or re-enables them, or resets their password (`API-06`); disabling signs them out everywhere. An Admin cannot demote or disable themselves.

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Sales, Admin, Session.
2. Requirement rows: `S-SEC-01` to `S-SEC-03` in [system requirements](/requirements/system.md); `N-07`; `B-30` and the [Roles](/requirements/business.md#roles) in [business requirements](/requirements/business.md).
3. Stores: [`app_user`](/architecture/sql-store.md#app_user), [`auth_session`](/architecture/sql-store.md#auth_session); `AUTH` and `USER` rows of [Audit actions](/architecture/sql-store.md#audit-actions).
4. Rules: [Retention and erasure](/architecture/rules.md#retention-and-erasure) for expired sessions.
5. Interfaces: [Conventions](/architecture/interfaces.md#conventions) (roles, authentication, CSRF) and [Authentication and users](/architecture/interfaces.md#authentication-and-users) (`API-01` to `API-06`).
6. Services: the [api](/architecture/services/api.md) (`SESSION_TTL_HOURS`, `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES`, `PASSWORD_MIN_LENGTH` in its [runtime](/architecture/services/api.md#runtime)); the frontend's [Routes](/architecture/services/frontend.md#routes), [Navigation](/architecture/services/frontend.md#navigation) and [States](/architecture/services/frontend.md#states).
7. Screens: [Sign in](#sign-in), [Users](#users).
8. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-52` to `AC-54`, `AC-67`.

## Sign in

Route `/login`. Anonymous.

**Layout**

```text
┌──────────────────────────────┐
│ LeadRadar                    │
│ Email    [                 ] │
│ Password [                 ] │
│                  [ Sign in ] │
└──────────────────────────────┘
```

WF-21 — Sign in

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-093` | Sign in shall submit email and password and, on success, go to the return path or `/prospects`. |
| `FR-094` | A failure shall show the api's message: wrong credentials, account locked with the minutes remaining, or account disabled. |

Obligations: `S-SEC-01`.

**Data**: `API-01`, `API-03`. **States**: [States](/architecture/services/frontend.md#states).

## Users

Route `/users`. Admin only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Users                                                          [ New user ]  │
├──────────────────────┬──────────────────────┬────────┬──────────┬────────────┤
│ Name                 │ Email                │ Role   │ Status   │ Last sign-in │
│ Ana Sales            │ sales@leadradar.local│ Sales  │ Active   │ today      │
│ Olga Admin           │ admin@leadradar.local│ Admin  │ Active   │ today      │
└──────────────────────┴──────────────────────┴────────┴──────────┴────────────┘
```

WF-22 — Users

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-095` | The screen shall list users with name, email, role, status and last sign-in. |
| `FR-096` | New user and Edit shall set display name, role and, on creation or reset, a password of at least `PASSWORD_MIN_LENGTH` characters; the email is fixed after creation. |
| `FR-097` | Disable shall confirm that the user will be signed out and unable to sign in; the signed-in Admin's own row shall offer neither Disable nor a role change. |

Obligations: `S-SEC-03`.

**Data**: `API-04`, `API-05`, `API-06`. **States**: [States](/architecture/services/frontend.md#states).
