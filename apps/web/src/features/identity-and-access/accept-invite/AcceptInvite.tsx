import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { useAcceptInvite, useInvitePreview, useMe } from "../../../api/authenticationAndUsers";
import { ApiError } from "../../../api/client";
import type { Schemas } from "../../../api/contract";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Input } from "../../../components/controls";
import { FormField } from "../../../components/FormField";
import { usePrefersReducedMotion } from "../../../components/motion/usePrefersReducedMotion";
import { Skeleton } from "../../../components/Skeleton";
import { enumLabel, formatRelative } from "../../../shell/format";
import { formErrors } from "../../../shell/formErrors";
import { DataView } from "../../../shell/states/DataView";
import { Mark, useDarkScheme } from "../../landing/darkStage";
import type { InviteScene } from "./inviteScene";
import "./acceptInvite.css";

const FIELDS = ["display_name", "password"] as const;
const TYPE_MS = 28;

/** FR-170: types the invitation as Landing's Quote step types its quote. */
function InviteCard({ preview }: { preview: Schemas["InvitePreview"] }) {
  const reduced = usePrefersReducedMotion();
  const text = `${preview.invited_by} invited you to LeadRadar as ${enumLabel(preview.role)}`;
  const [shown, setShown] = useState(reduced ? text.length : 0);
  useEffect(() => {
    if (reduced) {
      setShown(text.length);
      return;
    }
    const timer = window.setInterval(() => {
      setShown((count) => {
        if (count >= text.length) {
          window.clearInterval(timer);
          return count;
        }
        return count + 1;
      });
    }, TYPE_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [reduced, text]);
  const typing = shown < text.length;
  return (
    <figure className="ai-card">
      <blockquote className="ai-q" aria-label={text}>
        <span aria-hidden="true">
          {text.slice(0, shown)}
          {typing && <span className="ai-caret" />}
        </span>
      </blockquote>
      <figcaption className="ai-src">
        {preview.email}, {formatRelative(preview.created_at, new Date())}
      </figcaption>
    </figure>
  );
}

/** FR-172: rises one step per password character up to the minimum line, then turns Accent. */
function PasswordColumn({ length, minimum }: { length: number; minimum: number }) {
  const filled = Math.min(length, minimum);
  const reached = length >= minimum;
  return (
    <div className="ai-col-wrap" aria-hidden="true">
      <div className={reached ? "ai-col ai-reached" : "ai-col"}>
        {Array.from({ length: minimum }, (_, index) => (
          <span key={index} className={index < filled ? "ai-seg ai-on" : "ai-seg"} />
        ))}
      </div>
      <span className="ai-col-count num">
        {filled}/{minimum}
      </span>
    </div>
  );
}

function AcceptForm({
  token,
  preview,
  scene,
  onJoin,
}: {
  token: string;
  preview: Schemas["InvitePreview"];
  scene: InviteScene | null;
  onJoin: () => void;
}) {
  const accept = useAcceptInvite();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [joining, setJoining] = useState(false);
  const errors = formErrors(accept.error, FIELDS);

  useEffect(() => {
    scene?.setName(displayName);
  }, [scene, displayName]);

  function submit(event: FormEvent) {
    event.preventDefault();
    onJoin();
    accept.mutate(
      { token, display_name: displayName, password },
      {
        onSuccess: () => {
          setJoining(true);
          void (scene?.celebrate() ?? Promise.resolve()).then(() => {
            void navigate("/prospects", { replace: true });
          });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 text-title font-semibold">You&apos;re invited.</h1>
        <p className="m-0 text-text-secondary">
          Choose the name your team will see and a password for {preview.email}.
        </p>
      </div>
      <FormField label="Display name" error={errors.fields["display_name"]}>
        {(field) => (
          <Input
            {...field}
            name="display_name"
            autoComplete="name"
            value={displayName}
            onChange={(event) => {
              setDisplayName(event.target.value);
            }}
          />
        )}
      </FormField>
      <div className="flex items-end gap-4">
        <div className="min-w-0 flex-1">
          <FormField
            label="Password"
            hint={`At least ${String(preview.password_min_length)} characters.`}
            error={errors.fields["password"]}
          >
            {(field) => (
              <Input
                {...field}
                name="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
              />
            )}
          </FormField>
        </div>
        <PasswordColumn length={password.length} minimum={preview.password_min_length} />
      </div>
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={accept.isPending || joining}>
          Join LeadRadar
        </Button>
      </div>
    </form>
  );
}

/** FR-169: the link no longer names a pending invite. */
function Expired() {
  return (
    <div className="flex max-w-sm flex-col items-start gap-4">
      <h1 className="m-0 text-title font-semibold">This invite link no longer works.</h1>
      <p className="m-0 text-text-secondary">Ask your Admin for a new one.</p>
      <ButtonLink to="/login" variant="secondary">
        Sign in
      </ButtonLink>
    </div>
  );
}

function Invite({
  token,
  scene,
  onJoin,
}: {
  token: string;
  scene: InviteScene | null;
  onJoin: () => void;
}) {
  const preview = useInvitePreview(token);
  if (preview.error instanceof ApiError && preview.error.status === 404) {
    return <Expired />;
  }
  return (
    <DataView
      query={preview}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-64 w-full max-w-sm" />}
      empty={{ message: "This invite link no longer works.", action: null }}
    >
      {(data) => (
        <div className="ai-grid">
          <AcceptForm token={token} preview={data} scene={scene} onJoin={onJoin} />
          <InviteCard preview={data} />
        </div>
      )}
    </DataView>
  );
}

/**
 * Accept invite (WF-28, FL-20 step 4, FR-169 to FR-173): the token comes from the fragment and is
 * sent only in request bodies; the form renders before the scene loads, and without WebGL the
 * scene is left out.
 */
export function AcceptInvite() {
  useDarkScheme();
  const reduced = usePrefersReducedMotion();
  const token = useLocation().hash.replace(/^#/, "");
  const me = useMe();
  // Set when the visitor submits, so the user the acceptance signs in is sent to Prospects by the
  // form after the beam has swept, not at once as one who arrived signed in is (FR-173).
  const [joining, setJoining] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [scene, setScene] = useState<InviteScene | null>(null);
  const [webgl, setWebgl] = useState(true);

  useEffect(() => {
    const [stage, canvas, overlay] = [stageRef.current, canvasRef.current, overlayRef.current];
    if (stage === null || canvas === null || overlay === null) {
      return;
    }
    let mounted: InviteScene | null = null;
    let cancelled = false;
    import("./inviteScene")
      .then(({ mountInviteScene }) => {
        if (cancelled) {
          return;
        }
        mounted = mountInviteScene({ stage, canvas, overlay, reduced });
        if (mounted === null) {
          setWebgl(false);
        }
        setScene(mounted);
      })
      .catch(() => {
        setWebgl(false);
      });
    return () => {
      cancelled = true;
      mounted?.dispose();
    };
  }, [reduced]);

  const arrivedSignedIn = me.status === "success" && !joining;

  return (
    <div className="ai-page bg-page text-text">
      <div ref={stageRef} className="ai-stage">
        {webgl && <canvas ref={canvasRef} className="block size-full" aria-hidden="true" />}
        <div ref={overlayRef} className="ai-overlay" aria-hidden="true" />
        <div className="ai-scrim" />
      </div>
      <header className="ai-top">
        <div className="flex items-center gap-2.5 text-section font-semibold">
          <Mark />
          LeadRadar
        </div>
      </header>
      <main className="ai-main">
        {arrivedSignedIn ? (
          <Navigate to="/prospects" replace />
        ) : token === "" ? (
          <Expired />
        ) : (
          <Invite
            token={token}
            scene={scene}
            onJoin={() => {
              setJoining(true);
            }}
          />
        )}
      </main>
    </div>
  );
}
