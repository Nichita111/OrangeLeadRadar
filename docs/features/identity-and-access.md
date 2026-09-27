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

1. An anonymous visitor opening `/` sees [Landing](/architecture/services/frontend.md#landing), whose Sign in buttons open [Sign in](#sign-in). Opening any other route, they are sent to Sign in with that route as return path.
2. Correct credentials set the session cookie (`API-01`) and return the user to that page; wrong ones answer one message that does not reveal which was wrong; `LOGIN_MAX_FAILURES` failures in a row lock the account for `LOGIN_LOCK_MINUTES`.
3. Sign out revokes the session (`API-02`) and shows Sign in. A session ends by itself after `SESSION_TTL_HOURS`.

### FL-20 Manage users

1. An Admin opens [Users](#users) and creates a user with email, display name, role and an initial password (`API-05`).
2. The Admin changes a user's role, disables or re-enables them, or resets their password (`API-06`); disabling signs them out everywhere. An Admin cannot demote or disable themselves.
3. Instead of setting a password, the Admin may invite a person by email with a role (`API-79`) and hand them the link; LeadRadar sends no message. Users lists the pending invites (`API-83`), and the Admin may revoke one (`API-80`).
4. The invitee opens the link within `INVITE_TTL_HOURS` and sees [Accept invite](#accept-invite) (`API-81`); choosing a display name and a password signs them in as a new user of the invited role (`API-82`) and opens Prospects. A used, revoked or expired link shows that it no longer works.

## Reading order

1. Terms in the [glossary](/requirements/glossary.md): Sales, Admin, Session.
2. Requirement rows: `S-SEC-01` to `S-SEC-03`, `S-SEC-05` in [system requirements](/requirements/system.md); `N-07`; `B-30`, `B-41` and the [Roles](/requirements/business.md#roles) in [business requirements](/requirements/business.md).
3. Stores: [`app_user`](/architecture/sql-store.md#app_user), [`auth_session`](/architecture/sql-store.md#auth_session), [`user_invite`](/architecture/sql-store.md#user_invite); `AUTH` and `USER` rows of [Audit actions](/architecture/sql-store.md#audit-actions).
4. Rules: [Retention and erasure](/architecture/rules.md#retention-and-erasure) for expired sessions and invites; [store ownership](/architecture/overview.md#store-ownership) for who writes users and sessions.
5. Interfaces: [Conventions](/architecture/interfaces.md#conventions) (roles, authentication, CSRF) and [Authentication and users](/architecture/interfaces.md#authentication-and-users) (`API-01` to `API-06`, `API-79` to `API-83`).
6. Services: the [api](/architecture/services/api.md) (`SESSION_TTL_HOURS`, `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES`, `PASSWORD_MIN_LENGTH`, `INVITE_TTL_HOURS`, `APP_BASE_URL` in its [runtime](/architecture/services/api.md#runtime)); the frontend's [Routes](/architecture/services/frontend.md#routes), [Navigation](/architecture/services/frontend.md#navigation) and [States](/architecture/services/frontend.md#states); the frontend's [Landing](/architecture/services/frontend.md#landing).
7. Decisions: [ADR-20](/architecture/adrs/adr-20-landing-scene-mock-layer-and-demo-sign-in.md), [ADR-21](/architecture/adrs/adr-21-invite-links-and-the-invite-scene.md).
8. Screens: [Sign in](#sign-in), [Accept invite](#accept-invite), [Users](#users).
9. Acceptance rows in [acceptance criteria](/requirements/acceptance.md): `AC-52` to `AC-54`, `AC-67`, `AC-78`, `AC-79`.

## Sign in

Route `/login`. Anonymous.

**Layout**

```text
┌────────────────────────────────┬──────────────────────────────────┐
│ LeadRadar                      │ Sign in                          │
│                                │ (lead sentence)                  │
│ Know which accounts to call,   │                                  │
│ and exactly why.               │ Email                            │
│                                │ [                              ] │
│                                │ (hint)                           │
│                                │ Password                         │
│                                │ [                              ] │
│                                │ (hint)                           │
│  (Aurora background)           │                                  │
│                                │                       [ Sign in ]│
└────────────────────────────────┴──────────────────────────────────┘
```

WF-21 — Sign in

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-093` | Sign in shall submit email and password and, on success, go to the return path or `/prospects`. The return path is carried in the `return` query parameter of `/login` and is followed only when it is a path of this client; a signed-in user who opens Sign in goes to `/prospects`. |
| `FR-094` | A failure shall show the api's message: wrong credentials, account locked with the minutes remaining, or account disabled. |
| `FR-152` | Each field of Sign in shall carry a hint under it: the email field says that it is the address the Admin created, and the password field says that repeated failures lock the account for a short time. |
| `FR-160` | Sign in shall be two panels: a brand panel carrying the LeadRadar wordmark and the headline "Know which accounts to call, and exactly why." over the [Aurora background](/architecture/services/frontend.md#motion) in the Accent and Accent soft colours, and a panel with the form; the brand panel carries no other text and no sign-in shortcut. |

Obligations: `S-SEC-01`.

**Data**: `API-01`, `API-03`. **States**: [States](/architecture/services/frontend.md#states).

## Accept invite

Route `/invite`, with the invite token in the fragment. Anonymous. Dark in both schemes, over the Landing floor, disc and accounts, as [Landing](/architecture/services/frontend.md#landing) is.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ LeadRadar                                                                    │
├──────────────────────────────────┬───────────────────────────────────────────┤
│ You're invited.                  │  ┌─────────────────────────────────────┐  │
│                                  │  │ Olga Admin invited you to LeadRadar │  │
│ Display name                     │  │ as Sales▌                            │  │
│ [                              ] │  │ admin@leadradar.local, 2 days ago    │  │
│ Password                         │  └─────────────────────────────────────┘  │
│ [                              ] │                                           │
│ (hint)                           │   (scene: the disc and the accounts;      │
│                                  │    your name as a new point; beside the   │
│               [ Join LeadRadar ] │    form a column that rises with the      │
│                                  │    password to the minimum line)          │
└──────────────────────────────────┴───────────────────────────────────────────┘
```

WF-28 — Accept invite

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-169` | Accept invite shall read the token from the fragment, never send it in a path or query, and preview it with `API-81`; a `404` shows "This invite link no longer works. Ask your Admin for a new one." with a link to Sign in and no form. |
| `FR-170` | The invite card shall type "<inviter> invited you to LeadRadar as <role>" and show the invited email and when the invite was made, as the Quote step of Landing types its quote. |
| `FR-171` | The form shall ask for a display name and a password; the password hint states the minimum length the preview returns. Join LeadRadar calls `API-82` and, on success, opens Prospects; a failure shows the api's message as `FR-094` does, a `VALIDATION` error beside its field. |
| `FR-172` | The scene shall show the Landing floor, disc and accounts; the display name, while it is typed, is a new point with its label on the disc, and on success the beam sweeps it and it turns Accent before Prospects opens. A column beside the form rises one step for each character of the password up to a line at the minimum length, and turns Accent when it reaches the line; it shows length only, never the password. |
| `FR-173` | Accept invite shall load its scene lazily, render the form before the scene loads, and under `prefers-reduced-motion` or without WebGL keep the form, the card and the column with no scene motion; a signed-in user opening it is sent to Prospects. |

Obligations: `S-SEC-05`.

**Data**: `API-81`, `API-82`. **States**: [States](/architecture/services/frontend.md#states).

## Users

Route `/users`. Admin only.

**Layout**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Users                                         [ Invite user ]  [ New user ]  │
├──────────────────────┬──────────────────────┬────────┬──────────┬────────────┤
│ Name                 │ Email                │ Role   │ Status   │ Last sign-in │
│ Ana Sales            │ sales@leadradar.local│ Sales  │ Active   │ 2 hours ago│
│ Olga Admin           │ admin@leadradar.local│ Admin  │ Active   │ 2 hours ago│
└──────────────────────┴──────────────────────┴────────┴──────────┴────────────┘
```

WF-22 — Users

**Behaviour**

| ID | Requirement |
|---|---|
| `FR-095` | The screen shall list users with name, email, role, status and last sign-in, or Never when the user has not signed in. |
| `FR-096` | New user and Edit shall set display name, role and, on creation or reset, a password, whose minimum length `PASSWORD_MIN_LENGTH` the api enforces with a field error; Edit resets the password only when a new one is entered; the email is fixed after creation. |
| `FR-097` | Disable shall confirm that the user will be signed out and unable to sign in; the signed-in Admin's own row shall offer neither Disable nor a role change. |
| `FR-158` | A disabled user's row shall offer Enable, which applies at once and confirms with a toast. |
| `FR-174` | Invite user shall ask for an email and a role and, on success, show the link once with a Copy button and the words "Send this link yourself; LeadRadar sends no message. It works once, for <INVITE_TTL_HOURS> hours." |
| `FR-175` | Below the users, Pending invites shall list email, role, invited by and expiry, each with Revoke, which confirms that the link will stop working. |

Obligations: `S-SEC-03`, `S-SEC-05`.

**Data**: `API-04`, `API-05`, `API-06`, `API-79`, `API-80`, `API-83`. **States**: [States](/architecture/services/frontend.md#states).
