import type { FindingView } from "../../../api/prospectsAndEvidence";
import { useEvidence } from "../../../api/prospectsAndEvidence";
import { Skeleton } from "../../../components/Skeleton";
import { DataView } from "../../../shell/states/DataView";

/**
 * FR-074: the passage with its section path, the quote highlighted inside it, and a link to the
 * original page, credited to the GDELT Project when it found the document (ADR-19). A purged
 * document shows the quote, the link and a sentence that the full text is no longer stored.
 */
export function EvidencePanel({ finding }: { finding: FindingView }) {
  const evidence = useEvidence(finding.id);
  return (
    <DataView
      query={evidence}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-16 w-full" />}
      empty={{ message: "No evidence.", action: null }}
    >
      {(data) => {
        const { excerpt, quote_start: start, quote_end: end } = data;
        return (
          <div className="flex flex-col gap-2 rounded-control bg-page p-4">
            {data.purged || excerpt === null || start === null || end === null ? (
              <>
                <p className="m-0">&ldquo;{finding.quote}&rdquo;</p>
                <p className="m-0 text-text-secondary">
                  The full text of this page is no longer stored.
                </p>
              </>
            ) : (
              <>
                {data.section !== null && (
                  <p className="m-0 text-hint text-text-tertiary">{data.section}</p>
                )}
                <p className="m-0">
                  {excerpt.slice(0, start)}
                  <mark className="bg-highlight text-text">{excerpt.slice(start, end)}</mark>
                  {excerpt.slice(end)}
                </p>
              </>
            )}
            <p className="m-0">
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
              <p className="m-0 text-hint text-text-tertiary">
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
      }}
    </DataView>
  );
}
