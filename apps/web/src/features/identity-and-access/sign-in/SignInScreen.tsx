/**
 * [Sign in](/features/identity-and-access.md#sign-in). Route `/login`, anonymous. WF-21.
 */
import { Suspense, lazy, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useLogin } from "../../../api/auth";
import { ApiError } from "../../../api/client";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Input } from "../../../components/Input";
import { AuroraFallback } from "../../../components/motion/AuroraFallback";
import { BlurInText } from "../../../components/motion/BlurInText";
import { LazyLoadBoundary } from "../../../components/motion/LazyLoadBoundary";

const AuroraBackground = lazy(() => import("../../../components/motion/AuroraBackground"));

interface LocationState {
  from?: { pathname: string };
}

function isLocationState(value: unknown): value is LocationState {
  return typeof value === "object" && value !== null;
}

/** `FR-094`: on Sign in, a `403` can only mean the account is disabled — the route is anonymous,
 * so no role check can be refusing it — and the `LOCKED` message needs the minutes from
 * `details.retry_after_min`, which the api's own message text does not carry. */
function describeSignInError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Try again.";
  }
  if (error.status === 403) {
    return "This account has been disabled.";
  }
  if (error.code === "LOCKED") {
    const minutes = error.details?.retry_after_min;
    return typeof minutes === "number"
      ? `Too many failed sign-ins. Try again in ${String(minutes)} minute${minutes === 1 ? "" : "s"}.`
      : error.message;
  }
  return error.message;
}

export function SignInScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          const state = isLocationState(location.state) ? location.state : null;
          void navigate(state?.from?.pathname ?? "/prospects", { replace: true });
        },
      },
    );
  };

  return (
    <div className="flex min-h-screen">
      <div className="relative hidden flex-1 items-center justify-center overflow-hidden bg-surface lg:flex">
        <Suspense fallback={<AuroraFallback />}>
          <LazyLoadBoundary fallback={<AuroraFallback />}>
            <AuroraBackground />
          </LazyLoadBoundary>
        </Suspense>
        <div className="relative z-10 max-w-sm px-8 text-center">
          <p className="text-[24px] font-semibold text-text">LeadRadar</p>
          <BlurInText as="p" className="mt-3 text-sm text-text-secondary">
            Sales intelligence for your team, from public signals.
          </BlurInText>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-[24px] font-semibold text-text lg:hidden">LeadRadar</h1>
          <h2 className="mt-2 text-[15px] font-semibold text-text">Sign in</h2>
          <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            <Input
              id="email"
              type="email"
              label="Email"
              hint="The address the Admin created for you."
              autoComplete="email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
              required
            />
            <Input
              id="password"
              type="password"
              label="Password"
              hint="Repeated failures lock the account for a short time."
              autoComplete="current-password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
              required
            />
            {login.isError && <Callout kind="error">{describeSignInError(login.error)}</Callout>}
            <Button type="submit" variant="primary" disabled={login.isPending} className="mt-2">
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
