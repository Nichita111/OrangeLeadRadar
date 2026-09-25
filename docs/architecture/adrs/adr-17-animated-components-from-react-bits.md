---
type: Decision
title: ADR-17 Animated components from React Bits
description: The frontend animates with the Motion library and takes its animated components from React Bits, copied into the repository as owned code and used only for the patterns its Motion section lists.
status: draft
tags: []
---

# ADR-17 Animated components from React Bits

## Context

The users are sales managers without AI expertise. What changes on screen must be visible without being explained: a rescore moves an account up the ranking, a refresh is running, an alert has arrived. Static screens make these changes easy to miss. Writing every animation by hand costs more than the screens are worth, and an unlimited animation vocabulary makes the product noisy and hard to make accessible ([N-10](/requirements/system.md)).

## Decision

The frontend animates with the `motion` library. Animated components are taken from [React Bits](https://reactbits.dev), installed with its shadcn registry in the TypeScript and Tailwind variant and copied into `apps/web/src/components/motion/`, where they are owned code like the Radix-based primitives. Only the patterns of the frontend's [Motion](/architecture/services/frontend.md#motion) section may be used, each with its reduced-motion behaviour. A background that needs WebGL is allowed on Sign in only and is loaded lazily; the client makes no request to React Bits at run time.

## Consequences

- One small motion vocabulary, each pattern tied to what it communicates, so a new animation needs a new row in the Motion section first.
- Copied components are reviewed and tested like the rest of the client: keyboard behaviour, reduced motion and contrast are checked on the copy, not assumed from the source.
- React Bits is published under MIT with the Commons Clause. The owner confirms that this licence fits LeadRadar's use before the first component ships.
- The dependencies a copied component needs (`motion`, and `gsap`, `three` or `ogl` for the few that use them) are added only when a component that needs them is adopted.

## Alternatives considered

- **Hand-written CSS and Motion only.** Rejected: the same patterns rewritten one by one, without a shared vocabulary.
- **A scroll-driven, cinematic motion style.** Rejected: LeadRadar screens are working tools, and motion that is not tied to a state change slows the task.
- **No animation.** Rejected: rank changes, running states and new alerts would go unnoticed by the users this product is built for.
