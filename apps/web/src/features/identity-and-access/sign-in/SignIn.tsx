import { useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { useLogin, useMe } from "../../../api/authenticationAndUsers";
import { ApiError } from "../../../api/client";
import { Button, ButtonLink } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Input } from "../../../components/controls";
import { FormField } from "../../../components/FormField";
import { Aurora } from "../../../components/motion/Aurora";
import { BlurText } from "../../../components/motion/BlurText";
import { Skeleton } from "../../../components/Skeleton";
import { formErrors } from "../../../shell/formErrors";
import { safeReturnPath } from "../../../shell/returnPath";
import { DataView } from "../../../shell/states/DataView";

function BrandPanel() {
  return (
    <section className="relative flex flex-col justify-between overflow-hidden bg-surface p-14">
      <Aurora />
      <div className="relative text-section font-semibold">LeadRadar</div>
      <BlurText
        as="h2"
        text="Know which accounts to call, and exactly why."
        className="relative m-0 max-w-[16ch] text-title font-semibold"
      />
      <div />
    </section>
  );
}

function SignInForm({ login }: { login: ReturnType<typeof useLogin> }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const errors = formErrors(login.error, ["email", "password"]);

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          void navigate(safeReturnPath(params.get("return")), { replace: true });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex w-full max-w-sm flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="m-0 text-title font-semibold">Sign in</h1>
        <p className="m-0 text-text-secondary">
          Use the email and password your Admin created for you.
        </p>
      </div>
      <FormField
        label="Email"
        hint="The address your Admin created for you."
        error={errors.fields["email"]}
      >
        {(field) => (
          <Input
            {...field}
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        )}
      </FormField>
      <FormField
        label="Password"
        hint="Several failed attempts in a row lock the account for a short time."
        error={errors.fields["password"]}
      >
        {(field) => (
          <Input
            {...field}
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        )}
      </FormField>
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" disabled={login.isPending}>
          Sign in
        </Button>
      </div>
    </form>
  );
}

/** FL-19 step 1, FR-093, FR-094, FR-152, FR-160: two panels; a signed-in visitor goes to Prospects. */
export function SignIn() {
  const me = useMe();
  const login = useLogin();
  // A visitor who signs in now is sent by the submit, to the return path; only one who arrived
  // already signed in is sent to Prospects (FR-093).
  const signedIn = me.status === "success" && login.isIdle;
  const unauthenticated =
    me.status === "error" && me.error instanceof ApiError && me.error.status === 401;
  return (
    <div className="grid min-h-screen grid-cols-2">
      <BrandPanel />
      <section className="flex items-center justify-center p-8">
        {signedIn ? (
          <Navigate to="/prospects" replace />
        ) : (
          <FormOrCheck me={me} login={login} unauthenticated={unauthenticated} />
        )}
      </section>
    </div>
  );
}

function FormOrCheck({
  me,
  login,
  unauthenticated,
}: {
  me: ReturnType<typeof useMe>;
  login: ReturnType<typeof useLogin>;
  unauthenticated: boolean;
}) {
  if (unauthenticated || me.status === "success") {
    return <SignInForm login={login} />;
  }
  return (
    <DataView
      query={me}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-64 w-full max-w-sm" />}
      empty={{
        message: "There is no session.",
        action: <ButtonLink to="/login">Sign in</ButtonLink>,
      }}
    >
      {() => <SignInForm login={login} />}
    </DataView>
  );
}
