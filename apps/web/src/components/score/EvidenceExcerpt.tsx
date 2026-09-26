import type { Schemas } from "../../api/contract";

/** `FR-116`: the quoted sentence highlighted inside its passage; plain text when purged. */
export function EvidenceExcerpt({ evidence }: { evidence: Schemas["EvidenceView"] }) {
  const { excerpt, quote_start: start, quote_end: end } = evidence;
  if (excerpt === null || start === null || end === null) return <p>{excerpt}</p>;
  return (
    <p>
      {excerpt.slice(0, start)}
      <mark className="bg-highlight">{excerpt.slice(start, end)}</mark>
      {excerpt.slice(end)}
    </p>
  );
}
