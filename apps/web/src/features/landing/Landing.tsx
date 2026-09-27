import { useEffect, useRef, useState } from "react";

import { useDemoLogin } from "../../api/authenticationAndUsers";
import { ButtonLink } from "../../components/Button";
import { usePrefersReducedMotion } from "../../components/motion/usePrefersReducedMotion";
import { DemoShortcuts } from "../identity-and-access/sign-in/DemoShortcuts";
import "./landing.css";

/** The steps of WF-27, in order (FR-161). */
export const STEPS = [
  {
    name: "Accounts",
    title: "Know which accounts to call, and why.",
    lead: "Twenty accounts, one service to sell: Intelligent Automation.",
  },
  {
    name: "Sources",
    title: "LeadRadar reads what companies publish.",
    lead: "News, company sites, job boards and investor relations, fetched on a schedule.",
  },
  {
    name: "Read",
    title: "Every page is read, not guessed.",
    lead: "Each document is split into passages and kept with its address and date.",
  },
  {
    name: "Sift",
    title: "Only passages that answer a question stay.",
    lead: "Intelligent Automation asks nine questions. Passages that answer none are set aside.",
  },
  {
    name: "Quote",
    title: "Every signal carries a quote, source and date.",
    lead: "The quote stays in its own language, with an English translation beside it.",
  },
  {
    name: "Score",
    title: "Scores come from rules you can read.",
    lead: "Fit and Intent add up weighted rules. Models answer questions; they never set the score.",
  },
  {
    name: "Rank",
    title: "The accounts worth a call rise to the top.",
    lead: "LeadRadar never contacts anyone. Your team decides who to call.",
  },
  {
    name: "Prospects",
    title: "Your prospects, ranked and explained.",
    lead: "Open the live demo as a Sales or an Admin user.",
  },
] as const;

function progressOf(scroll: HTMLElement): number {
  const rect = scroll.getBoundingClientRect();
  const range = rect.height - window.innerHeight;
  return range > 0 ? Math.min(1, Math.max(0, -rect.top / range)) : 0;
}

function Mark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="size-5">
      <circle cx="12" cy="12" r="9.5" className="stroke-text-tertiary" />
      <circle cx="12" cy="12" r="5" className="stroke-text-tertiary" />
      <circle cx="15.6" cy="8.4" r="2.2" className="fill-accent" />
    </svg>
  );
}

/**
 * Landing (WF-27, FR-161 to FR-166): eight steps over one pinned scene, dark in both schemes. The words
 * render at once; the scene loads after them and, without WebGL, is left out.
 */
export function Landing() {
  const reduced = usePrefersReducedMotion();
  const demoLogin = useDemoLogin();
  const scrollRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);
  const [webgl, setWebgl] = useState(true);

  // FR-106: Landing is dark in both schemes.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset["scheme"] = "dark";
    return () => {
      delete root.dataset["scheme"];
    };
  }, []);

  useEffect(() => {
    const scroll = scrollRef.current;
    if (scroll === null) {
      return;
    }
    const onScroll = () => {
      setStep(Math.round(progressOf(scroll) * (STEPS.length - 1)));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  useEffect(() => {
    const [scroll, stage, canvas, overlay] = [
      scrollRef.current,
      stageRef.current,
      canvasRef.current,
      overlayRef.current,
    ];
    if (scroll === null || stage === null || canvas === null || overlay === null) {
      return;
    }
    let unmount: (() => void) | null = null;
    let cancelled = false;
    import("./scene")
      .then(({ mountScene }) => {
        if (cancelled) {
          return;
        }
        unmount = mountScene({ scroll, stage, canvas, overlay, steps: STEPS.length, reduced });
        if (unmount === null) {
          setWebgl(false);
        }
      })
      .catch(() => {
        // FR-128: a scene that fails to load leaves the words on the dark Page.
        setWebgl(false);
      });
    return () => {
      cancelled = true;
      unmount?.();
    };
  }, [reduced]);

  function goTo(index: number) {
    const scroll = scrollRef.current;
    if (scroll === null) {
      return;
    }
    const range = scroll.offsetHeight - window.innerHeight;
    window.scrollTo({
      top: scroll.offsetTop + range * (index / (STEPS.length - 1)),
      behavior: reduced ? "auto" : "smooth",
    });
  }

  return (
    <div className="lr-landing bg-page text-text">
      <header className="lr-top">
        <div className="flex items-center gap-2.5 text-section font-semibold">
          <Mark />
          LeadRadar
        </div>
        <ButtonLink to="/login" variant="primary">
          Sign in
        </ButtonLink>
      </header>

      <nav className="lr-dots" aria-label="Steps">
        {STEPS.map((s, index) => (
          <button
            key={s.name}
            type="button"
            className="lr-dot"
            aria-label={s.name}
            aria-current={index === step ? "step" : undefined}
            onClick={() => {
              goTo(index);
            }}
          />
        ))}
      </nav>

      <main ref={scrollRef} className="relative">
        <div ref={stageRef} className="lr-stage">
          {webgl && <canvas ref={canvasRef} className="block size-full" aria-hidden="true" />}
          {webgl && <div className="lr-scrim" />}
          <div ref={overlayRef} className="lr-overlay" aria-hidden="true" />
        </div>
        <div className="lr-steps">
          {STEPS.map((s, index) => (
            <section key={s.name} className="lr-step" aria-labelledby={`lr-step-${String(index)}`}>
              <div className="lr-copy">
                {index === 0 ? (
                  <h1 id={`lr-step-${String(index)}`}>{s.title}</h1>
                ) : (
                  <h2 id={`lr-step-${String(index)}`}>{s.title}</h2>
                )}
                <p className="lr-lead">{s.lead}</p>
                {index === STEPS.length - 1 && (
                  <div className="flex flex-wrap gap-2.5 pt-1.5">
                    <ButtonLink to="/login" variant="primary">
                      Sign in
                    </ButtonLink>
                    <DemoShortcuts demoLogin={demoLogin} className="flex flex-wrap gap-2.5" />
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
