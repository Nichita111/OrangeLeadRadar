import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type FormEvent, type ReactElement } from "react";

import { useCreateMarket, useUpdateMarket } from "../../../api/industriesAndMarkets";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { CheckboxGroup } from "../../../components/CheckboxGroup";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input } from "../../../components/controls";
import { useToast } from "../../../components/Toast";
import { COUNTRY_CODES } from "../../../shell/countries";
import { formErrors } from "../../../shell/formErrors";
import { countryName } from "../../../shell/format";
import { toUpperSnakeInput } from "../../../shell/upperSnake";

const FIELDS = ["code", "name", "country_codes"] as const;

const COUNTRY_OPTIONS = COUNTRY_CODES.map((code) => ({
  value: code,
  label: `${countryName(code)} (${code})`,
}));

interface MarketDialogProps {
  /** Omitted when a `RowMenu` item opens the dialog under fully controlled `open` instead. */
  trigger?: ReactElement;
  /** Absent in New mode; the market being renamed in Rename mode. */
  market?: Schemas["Market"];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/** FR-155, FR-156: New market and Rename share one form; the code cannot change once set. */
export function MarketDialog({ trigger, market, open, onOpenChange }: MarketDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const currentOpen = open ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const editing = market !== undefined;
  return (
    <Dialog
      {...(trigger === undefined ? {} : { trigger })}
      title={editing ? "Rename market" : "New market"}
      description={
        editing
          ? "Only the name and countries change; the code stays the same."
          : "The code accepts UPPER_SNAKE only and cannot be changed later."
      }
      open={currentOpen}
      onOpenChange={setOpen}
    >
      <MarketForm
        {...(market === undefined ? {} : { market })}
        onDone={() => {
          setOpen(false);
        }}
      />
    </Dialog>
  );
}

function MarketForm({ market, onDone }: { market?: Schemas["Market"]; onDone: () => void }) {
  const { notify } = useToast();
  const create = useCreateMarket();
  const update = useUpdateMarket();
  const [code, setCode] = useState(market?.code ?? "");
  const [name, setName] = useState(market?.name ?? "");
  const [countryCodes, setCountryCodes] = useState<string[]>(market?.country_codes ?? []);
  const errors = formErrors(market === undefined ? create.error : update.error, FIELDS);
  const pending = create.isPending || update.isPending;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (market === undefined) {
      create.mutate(
        { code, name, country_codes: countryCodes },
        {
          onSuccess: () => {
            notify("Market created");
            onDone();
          },
        },
      );
      return;
    }
    const body: Schemas["MarketUpdate"] = {
      ...(name !== market.name && { name }),
      ...(countryCodes.join(",") !== market.country_codes.join(",") && {
        country_codes: countryCodes,
      }),
    };
    if (Object.keys(body).length === 0) {
      onDone();
      return;
    }
    update.mutate(
      { code: market.code, body },
      {
        onSuccess: () => {
          notify("Market updated");
          onDone();
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField
        label="Code"
        {...(market === undefined ? { hint: "Cannot be changed later." } : {})}
        error={errors.fields["code"]}
      >
        {(field) => (
          <Input
            {...field}
            type="text"
            readOnly={market !== undefined}
            value={code}
            onChange={(event) => {
              setCode(toUpperSnakeInput(event.target.value));
            }}
          />
        )}
      </FormField>
      <FormField label="Name" error={errors.fields["name"]}>
        {(field) => (
          <Input
            {...field}
            type="text"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        )}
      </FormField>
      <CheckboxGroup
        label="Countries"
        options={COUNTRY_OPTIONS}
        selected={countryCodes}
        onChange={setCountryCodes}
        error={errors.fields["country_codes"]}
      />
      {errors.callout !== undefined && <Callout kind="error">{errors.callout}</Callout>}
      <div className="flex justify-end gap-2">
        <DialogPrimitive.Close asChild>
          <Button type="button" variant="secondary">
            Cancel
          </Button>
        </DialogPrimitive.Close>
        <Button type="submit" variant="primary" disabled={pending}>
          {market === undefined ? "Create market" : "Save"}
        </Button>
      </div>
    </form>
  );
}
