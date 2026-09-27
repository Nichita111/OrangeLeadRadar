---
type: Decision
title: ADR-20 Landing scene, mock layer and demo sign-in
description: The live demo opens on a three.js landing page animated with Anime.js, every REST contract is declared from the start and answers 501 until built while a development-only mock answers the contracts not yet built, and demo shortcuts sign in without a password in replay mode only.
status: draft
tags: [identity-and-access]
---

# ADR-20 Landing scene, mock layer and demo sign-in

## Context

The jury meets LeadRadar through the live demo. [ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md) keeps app screens calm and allows WebGL only on Sign in. The frontend must be built before the api's features, without writing a contract shape twice. The presenter switches between the Sales and Admin users during the [demo walkthrough](/architecture/overview.md#demo-walkthrough).

## Decision

1. `/` is a Landing page whose one scene is built with three.js and animated by one Anime.js timeline scrubbed by scroll. It is loaded lazily, and it is the only screen outside ADR-17's pattern list and the only other WebGL screen; React Bits remains the only source of animated components on app screens.
2. Every REST contract is declared in the api from the start and answers `501 NOT_IMPLEMENTED` until built, so the OpenAPI document and the client generated from it are complete, and the client holds no hand-written copy of a shape. In development only, Mock Service Worker answers the contracts not yet built, from handlers typed with that client; the production build carries no mock. A family's handlers are deleted when the api builds the family.
3. `API-78` signs in as a demo dataset user without a password, only in `FIXTURE_MODE` `replay`; the client shows the shortcuts, on Sign in only, only when `DEMO_SIGN_IN` is true.

## Consequences

three.js and Anime.js weigh only on the Landing chunk. Reduced motion shows still end frames; without WebGL the steps show their words alone. Screens switch from mocks to the api with no change, and a contract change regenerates the client and breaks the mocks at type-check. In replay, anyone who reaches the stack can sign in as Admin, the demo cloud machine included, which is accepted because it holds only the demo dataset. `AC-53` cannot pass for a stubbed contract until its feature is built.

## Alternatives considered

- **A scroll-driven site template library (Scrolltide) and GSAP.** Rejected: a second animation vocabulary and licence risk.
- **A hand-written mock server.** Rejected: it duplicates shapes already declared in [interfaces](/architecture/interfaces.md).
- **Typing the seeded passwords into Sign in from the client.** Rejected: the client would hold a secret ([frontend Responsibilities](/architecture/services/frontend.md#responsibilities)).
- **A hand-written OpenAPI fragment per pending family in the client.** Rejected: a second copy of each shape ([TypeScript Types](/guidelines/typescript.md#types)).
- **A runtime switch that starts the mocks in the built image.** Rejected: no requirement runs the built stack on mocks, and the production build would carry the mock.
