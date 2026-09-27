import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useState, type ReactElement } from "react";

import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Dialog } from "../../../components/Dialog";
import { FormField } from "../../../components/FormField";
import { Input, Select } from "../../../components/controls";
import { strengthLabel } from "../../../shell/format";
import { toUpperSnakeInput } from "../../../shell/upperSnake";

type Disqualifier = Schemas["Disqualifier"];
type DisqualifierKind = Schemas["DisqualifierKind"];

const MIN_STRENGTHS: Schemas["FindingStrength"][] = ["WEAK", "MEDIUM", "STRONG"];

interface DisqualifierDialogProps {
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  disqualifier?: Disqualifier;
  criteria: Schemas["ICPCriterion"][];
  questions: Schemas["SignalQuestion"][];
  onSave: (disqualifier: Disqualifier) => void;
}

/** FR-032, G5: adds or edits one exclusion rule (`ICP_MISMATCH` or `SIGNAL`). */
export function DisqualifierDialog({
  trigger,
  open,
  onOpenChange,
  disqualifier,
  criteria,
  questions,
  onSave,
}: DisqualifierDialogProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const currentOpen = open ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const editing = disqualifier !== undefined;

  const [key, setKey] = useState(disqualifier?.key ?? "");
  const [label, setLabel] = useState(disqualifier?.label ?? "");
  const [kind, setKind] = useState<DisqualifierKind>(disqualifier?.kind ?? "ICP_MISMATCH");
  const [criterionKey, setCriterionKey] = useState(disqualifier?.criterion_key ?? "");
  const [questionKey, setQuestionKey] = useState(disqualifier?.question_key ?? "");
  const [minStrength, setMinStrength] = useState<Schemas["FindingStrength"]>(
    disqualifier?.min_strength ?? "WEAK",
  );

  function submit() {
    onSave(
      kind === "ICP_MISMATCH"
        ? { key, label, kind, criterion_key: criterionKey }
        : { key, label, kind, question_key: questionKey, min_strength: minStrength },
    );
    setOpen(false);
  }

  return (
    <Dialog
      {...(trigger === undefined ? {} : { trigger })}
      title={editing ? "Edit exclusion rule" : "New exclusion rule"}
      description="Excludes an account whose signals match this rule."
      open={currentOpen}
      onOpenChange={setOpen}
    >
      <div className="flex flex-col gap-4">
        <FormField label="Key">
          {(field) => (
            <Input
              {...field}
              type="text"
              value={key}
              onChange={(event) => {
                setKey(toUpperSnakeInput(event.target.value));
              }}
            />
          )}
        </FormField>
        <FormField label="Label">
          {(field) => (
            <Input
              {...field}
              type="text"
              value={label}
              onChange={(event) => {
                setLabel(event.target.value);
              }}
            />
          )}
        </FormField>
        <FormField label="Kind">
          {(field) => (
            <Select
              {...field}
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as DisqualifierKind);
              }}
            >
              <option value="ICP_MISMATCH">ICP mismatch</option>
              <option value="SIGNAL">Signal</option>
            </Select>
          )}
        </FormField>
        {kind === "ICP_MISMATCH" ? (
          <FormField label="Criterion">
            {(field) => (
              <Select
                {...field}
                value={criterionKey}
                onChange={(event) => {
                  setCriterionKey(event.target.value);
                }}
              >
                <option value="">Choose a criterion…</option>
                {criteria.map((criterion) => (
                  <option key={criterion.key} value={criterion.key}>
                    {criterion.key}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
        ) : (
          <>
            <FormField label="Question">
              {(field) => (
                <Select
                  {...field}
                  value={questionKey}
                  onChange={(event) => {
                    setQuestionKey(event.target.value);
                  }}
                >
                  <option value="">Choose a question…</option>
                  {questions.map((question) => (
                    <option key={question.key} value={question.key}>
                      {question.key}
                    </option>
                  ))}
                </Select>
              )}
            </FormField>
            <FormField label="Minimum strength">
              {(field) => (
                <Select
                  {...field}
                  value={minStrength}
                  onChange={(event) => {
                    setMinStrength(event.target.value as Schemas["FindingStrength"]);
                  }}
                >
                  {MIN_STRENGTHS.map((strength) => (
                    <option key={strength} value={strength}>
                      {strengthLabel(strength)}
                    </option>
                  ))}
                </Select>
              )}
            </FormField>
          </>
        )}
        <div className="flex justify-end gap-2">
          <DialogPrimitive.Close asChild>
            <Button type="button" variant="secondary">
              Cancel
            </Button>
          </DialogPrimitive.Close>
          <Button type="button" variant="primary" onClick={submit}>
            Save
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
