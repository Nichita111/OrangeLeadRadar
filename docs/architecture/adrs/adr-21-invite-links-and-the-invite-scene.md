---
type: Decision
title: ADR-21 Invite links and the invite scene
description: An Admin invites a person by a single-use link that the Admin hands over, the token travels only in the link's fragment and request bodies, and the page that accepts it reuses the Landing scene.
status: draft
tags: [identity-and-access]
---

# ADR-21 Invite links and the invite scene

## Context

Users exist only when an Admin creates them with a password the Admin chooses and must pass on. The owner wants people to join LeadRadar themselves, in the spirit of [Landing](/architecture/services/frontend.md#landing), without opening registration to anyone: LeadRadar holds sales intelligence and has an Admin role. LeadRadar sends no message ([ADR-10](/architecture/adrs/adr-10-minimal-contact-data.md) keeps contact data minimal), and the api logs every request path.

## Decision

1. An Admin invites an email with a role; the api returns a single-use link `APP_BASE_URL/invite#<token>` once, stores only the token's hash, and the Admin hands the link over. The invite expires after `INVITE_TTL_HOURS` and can be revoked while pending.
2. The token travels in the link's fragment and in request bodies only, never in a path or query, so no server or proxy log records it.
3. Accepting creates an active user with the invited email and role and signs them in, exactly as a sign-in would.
4. Everyone signs in with credentials: the demo sign-in of [ADR-20](/architecture/adrs/adr-20-landing-scene-mock-layer-and-demo-sign-in.md) decision 3 is withdrawn, with `API-78`, its shortcuts and `DEMO_SIGN_IN`; the presenter signs in as the demo users with their seeded passwords.
5. [Accept invite](/features/identity-and-access.md#accept-invite) reuses the Landing scene module: it is the second screen outside [ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)'s pattern list and the only other screen to import three.js and Anime.js, lazily.

## Consequences

Anyone holding the link before it is used can join with the invited role, so the Admin hands it over privately; the short expiry and single use bound the risk. There is still no open registration and no email service, and no way in without a password: anyone reaching the demo stack no longer becomes Admin. A new table, [`user_invite`](/architecture/sql-store.md#user_invite), and five contracts, `API-79` to `API-83`, join the Authentication and users family.

## Alternatives considered

- **Open self sign-up as Sales.** Rejected: anyone reaching the stack would read the prospect data.
- **Request access approved by an Admin.** Deferred: it adds a queue for the Admin and can be added on top of invites.
- **Sending the link by email.** Rejected: LeadRadar sends no message, and it would need an email provider and its secret.
- **The token in the URL path.** Rejected: the api and the `web` proxy log paths.
