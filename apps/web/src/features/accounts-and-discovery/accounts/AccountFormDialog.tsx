/**
 * The New account dialog of [Accounts](/features/accounts-and-discovery.md#accounts) (`FR-039`,
 * `FR-138`).
 */
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAccount, useCreateAccount } from "../../../api/accounts";
import { Button } from "../../../components/Button";
import { Dialog } from "../../../components/Dialog";
import { Input } from "../../../components/Input";

export function AccountFormDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const createAccount = useCreateAccount();
  const [domain, setDomain] = useState("");
  const [name, setName] = useState("");
  const [domainError, setDomainError] = useState<string | undefined>(undefined);
  const [conflictId, setConflictId] = useState<string | undefined>(undefined);
  const existing = useAccount(conflictId);

  const reset = () => {
    setDomain("");
    setName("");
    setDomainError(undefined);
    setConflictId(undefined);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (conflictId !== undefined) {
      onOpenChange(false);
      void navigate(`/accounts/${conflictId}/profile`);
      return;
    }
    createAccount.mutate(
      { domain, name, aliases: [], sources: [] },
      {
        onSuccess: (account) => {
          reset();
          onOpenChange(false);
          void navigate(`/accounts/${account.id}/profile`);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 409) {
            const entityId =
              typeof error.details?.entity_id === "string" ? error.details.entity_id : undefined;
            setConflictId(entityId);
            setDomainError(error.message);
            return;
          }
          setDomainError(error instanceof ApiError ? error.message : "Something went wrong.");
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
        }
        onOpenChange(next);
      }}
      title="New account"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          id="account-domain"
          label="Domain or URL"
          value={domain}
          onChange={(event) => {
            setDomain(event.target.value);
            setConflictId(undefined);
            setDomainError(undefined);
          }}
          error={
            domainError !== undefined
              ? conflictId !== undefined && existing.data !== undefined
                ? `This domain is already an account: ${existing.data.name}.`
                : domainError
              : undefined
          }
          required
        />
        <Input
          id="account-name"
          label="Name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
          required
        />
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={createAccount.isPending}>
            {conflictId !== undefined ? "Open existing account" : "Create account"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
