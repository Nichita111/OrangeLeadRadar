---
type: Guideline
title: TypeScript guidelines
description: How TypeScript spells the coding guidelines for the web client - toolchain, types, the generated API client, React and server state, routing, styling, accessibility and tests.
status: draft
tags: []
---

# TypeScript guidelines

The web client lives in `apps/web`. This file says how the [coding guidelines](/guidelines/coding.md) are spelled in TypeScript and React.

## Toolchain

- Node 22 LTS, npm, Vite; TypeScript with `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
- ESLint with the TypeScript, React Hooks and jsx-a11y rule sets; Prettier for formatting.
- Vitest with Testing Library for unit and component tests.
- *planned*: `npm run validate` runs type check, lint, format check and tests.

## Types

- No `enum`: closed sets are string literal unions, taken from the generated client.
- No `any`, no double assertion (`as unknown as T`), no non-null assertion on data from the api.
- Every type of data from the api comes from the client generated with `openapi-typescript` from the api's OpenAPI document; a hand-written copy of a contract shape is a defect.

## React and server state

- Function components and hooks only.
- Server state lives in TanStack Query, one query key family per interface family; components never hold a copy of server data in local state.
- Polling of runs and alerts uses the query's refetch interval, set from `RUN_POLL_INTERVAL_MS` and `ALERT_POLL_INTERVAL_MS`.
- The screen composes no score, band or standing; it renders the contract's values. The "In short" text of Account detail is a pure function of the breakdown, unit-tested.

## Structure

```
apps/web/src/
├── api/                  generated client and query hooks per interface family
├── shell/                navigation, service selector, states, formatting, confirmation
├── features/<slug>/      one folder per feature file, one component folder per screen
├── components/           shared primitives on Radix
└── components/motion/    animated components copied from React Bits, owned like the primitives
```

A screen's folder is named after its heading; its components carry the `FR-` identifiers they implement in their test names.

## Routing

React Router with the routes of the frontend's [Routes](/architecture/services/frontend.md#routes) table; Admin routes are guarded in the router, and the api enforces the role regardless.

## Styling and accessibility

- Tailwind CSS with design tokens for colour, spacing and type; components built on Radix primitives for keyboard and screen-reader behaviour.
- Colour, type and radius come from the tokens of the frontend's [Visual language](/architecture/services/frontend.md#visual-language); a component never names a literal colour.
- Icons come from `@phosphor-icons/react` only; an icon-only button carries an accessible name.
- Band and standing always carry a text label or shape besides colour.
- Animation is limited to the patterns of the frontend's [Motion](/architecture/services/frontend.md#motion), each component reading `prefers-reduced-motion` and covered by a test of its reduced-motion state.
- Every interactive element is reachable by keyboard with a visible focus ring.

## Tests

- Unit and component tests beside the source, named `<Component>.test.tsx`, never calling the network; api responses come from typed fixtures built from the generated types.
- End-to-end tests are QA's, in `tests/e2e/`, written from acceptance criteria ([Testing guidelines](/guidelines/testing.md)).
