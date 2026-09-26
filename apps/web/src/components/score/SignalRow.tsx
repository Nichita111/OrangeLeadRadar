import { MinusCircleIcon, PlusCircleIcon } from "@phosphor-icons/react";
import type { Schemas } from "../../api/contract";

type Question = Schemas["ScoreViewQuestionBreakdown"];

export function SignalRow({ question }: { question: Question }) {
  const positive = question.polarity === "POSITIVE";
  const Icon = positive ? PlusCircleIcon : MinusCircleIcon;
  return (
    <div className="flex items-center gap-2">
      <Icon
        aria-label={positive ? "Positive signal" : "Negative signal"}
        weight="fill"
        className={positive ? "text-positive" : "text-negative"}
      />
      <span>{question.question_text}</span>
      <span className="ml-auto font-mono tabular-nums">
        {question.points >= 0 ? "+" : ""}
        {question.points}
      </span>
    </div>
  );
}
