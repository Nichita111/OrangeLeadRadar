/**
 * [React Bits](https://reactbits.dev) "Stepper" (Components), copied into owned code
 * ([ADR-17](/architecture/adrs/adr-17-animated-components-from-react-bits.md)): position in a
 * process (`FR-124`) — the stages of a run on [Runs](/features/signal-pipeline.md#runs) (`FR-055`)
 * and the three parts of [Account import](/features/accounts-and-discovery.md#account-import)
 * (`FR-139`). A step settles in with a brief fade and scale on becoming done or current, never a
 * loop, so it never competes with the one perpetual [`ShimmerLabel`](./ShimmerLabel.tsx) a screen
 * may show at a time (`FR-126`). Collapses to the end state under `prefers-reduced-motion`
 * (`FR-125`).
 */
import { CheckIcon, CircleIcon } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";

/** The Motion section's "Enter" design value. */
const ENTER_S = 0.2;
const EASE = [0.16, 1, 0.3, 1] as const;

export type StepState = "done" | "current" | "pending";

export interface StepperStep {
  key: string;
  label: string;
  state: StepState;
}

function StepMark({ state }: { state: StepState }) {
  if (state === "done") {
    return <CheckIcon size={16} weight="bold" className="text-positive" aria-hidden="true" />;
  }
  if (state === "current") {
    return <CircleIcon size={16} weight="fill" className="text-accent" aria-hidden="true" />;
  }
  return <CircleIcon size={16} className="text-text-tertiary" aria-hidden="true" />;
}

export function Stepper({ steps }: { steps: StepperStep[] }) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2 text-sm">
      {steps.map((step, index) => {
        const item =
          prefersReducedMotion === true ? (
            <span className="flex items-center gap-1.5">
              <StepMark state={step.state} />
              <span className={step.state === "pending" ? "text-text-tertiary" : "text-text"}>
                {step.label}
              </span>
            </span>
          ) : (
            <motion.span
              className="flex items-center gap-1.5"
              initial={step.state === "pending" ? false : { opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: ENTER_S, ease: EASE }}
            >
              <StepMark state={step.state} />
              <span className={step.state === "pending" ? "text-text-tertiary" : "text-text"}>
                {step.label}
              </span>
            </motion.span>
          );
        return (
          <li key={step.key} className="flex items-center gap-1.5">
            {index > 0 && <span aria-hidden="true" className="mx-0.5 h-px w-4 bg-border" />}
            {item}
          </li>
        );
      })}
    </ol>
  );
}
