import { useNavigate, useSearchParams } from "react-router";

import type { useDemoLogin } from "../../../api/authenticationAndUsers";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { useConfig } from "../../../configContext";
import { formErrors } from "../../../shell/formErrors";
import { safeReturnPath } from "../../../shell/returnPath";

const SHORTCUTS: { role: Schemas["AppUserRole"]; label: string }[] = [
  { role: "SALES", label: "Enter as Sales" },
  { role: "ADMIN", label: "Enter as Admin" },
];

/**
 * FR-167, FR-168, FR-162: Enter as Sales and Enter as Admin when `DEMO_SIGN_IN` is true; each calls
 * `API-78` and goes to the return path or Prospects, and a failure shows the api's message.
 */
export function DemoShortcuts({
  demoLogin,
  className,
}: {
  demoLogin: ReturnType<typeof useDemoLogin>;
  className?: string;
}) {
  const { DEMO_SIGN_IN } = useConfig();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  if (!DEMO_SIGN_IN) {
    return null;
  }
  const errors = formErrors(demoLogin.error, []);
  return (
    <>
      <div className={className}>
        {SHORTCUTS.map(({ role, label }) => (
          <Button
            key={role}
            type="button"
            variant="secondary"
            disabled={demoLogin.isPending}
            onClick={() => {
              demoLogin.mutate(
                { role },
                {
                  onSuccess: () => {
                    void navigate(safeReturnPath(params.get("return")), { replace: true });
                  },
                },
              );
            }}
          >
            {label}
          </Button>
        ))}
      </div>
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
    </>
  );
}
