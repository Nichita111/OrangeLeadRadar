/**
 * `FR-074`: the passage with its section path, the quote highlighted inside it, and a link to
 * the original page, credited to the GDELT Project when it found the document
 * ([ADR-19](/architecture/adrs/adr-19-source-provider-terms-and-limits.md)). A purged document
 * shows the quote, the link and a sentence that the full text is no longer stored.
 */
import { useEvidence, type FindingView } from "../../../api/prospects";
import { QueryErrorState } from "../../../components/States";

export function EvidencePanel({ finding }: { finding: FindingView }) {
  const evidence = useEvidence(finding.id);

  if (evidence.isError) {
    return <QueryErrorState error={evidence.error} onRetry={() => void evidence.refetch()} />;
  }
  if (evidence.data === undefined) {
    return <div className="h-16 rounded-control bg-page" aria-hidden="true" />;
  }
  const { data } = evidence;
  const { excerpt, quote_start: start, quote_end: end } = data;

  return (
    <div className="flex flex-col gap-2 rounded-control bg-page p-4 text-sm text-text">
      {data.purged || excerpt === null || start === null || end === null ? (
        <>
          <p>&ldquo;{finding.quote}&rdquo;</p>
          <p className="text-text-secondary">The full text of this page is no longer stored.</p>
        </>
      ) : (
        <>
          {data.section !== null && (
            <p className="text-[12.5px] text-text-tertiary">{data.section}</p>
          )}
          <p>
            {excerpt.slice(0, start)}
            <mark className="bg-highlight text-text">{excerpt.slice(start, end)}</mark>
            {excerpt.slice(end)}
          </p>
        </>
      )}
      <p>
        <a
          href={data.document.url}
          target="_blank"
          rel="noreferrer"
          className="text-accent-ink underline"
        >
          Open original
        </a>
      </p>
      {data.document.plugin_code === "GDELT" && (
        <p className="text-[12.5px] text-text-tertiary">
          Found by the{" "}
          <a
            href="https://www.gdeltproject.org/"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            GDELT Project
          </a>
        </p>
      )}
    </div>
  );
}
