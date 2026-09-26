/**
 * [Service editor](/features/service-configuration.md#service-editor). Route `/services/:id`,
 * Admin only. Tabs Overview and Signal questions live here; Scoring is a link to the separate
 * [Scoring settings](/features/service-configuration.md#scoring-settings) route. WF-03.
 */
import { useParams, useSearchParams, Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useService } from "../../../api/services";
import { ErrorState, UnavailableState } from "../../../components/States";
import { OverviewTab } from "./OverviewTab";
import { QuestionsTab } from "./QuestionsTab";

type TabKey = "overview" | "questions";

export function ServiceEditorScreen() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: TabKey = searchParams.get("tab") === "questions" ? "questions" : "overview";

  const { data: service, isLoading, isError, error, refetch } = useService(id ?? "");

  if (id === undefined) {
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      {isLoading && <div className="h-24 rounded-card bg-page" />}
      {isError &&
        (error instanceof ApiError && (error.status === 503 || error.status === 429) ? (
          <UnavailableState
            dependency={
              typeof error.details?.dependency === "string"
                ? error.details.dependency
                : "The database"
            }
            stillWorks={[]}
          />
        ) : (
          <ErrorState
            message={error instanceof ApiError ? error.message : "Something went wrong."}
            onRetry={() => void refetch()}
          />
        ))}
      {!isLoading && !isError && service !== undefined && (
        <>
          <div>
            <Link to="/services" className="text-sm text-text-secondary hover:underline">
              Services
            </Link>
            <h1 className="mt-1 text-[24px] font-semibold text-text">{service.name}</h1>
            <p className="mt-1 text-sm text-text-secondary">
              Edit the service's details, its signal questions and its scoring.
            </p>
          </div>

          <div className="flex gap-2 border-b border-border">
            <button
              type="button"
              onClick={() => {
                setSearchParams({});
              }}
              className={`px-3 py-2 text-sm font-medium ${
                tab === "overview"
                  ? "border-b-2 border-accent text-text"
                  : "text-text-secondary hover:text-text"
              }`}
              aria-current={tab === "overview" ? "page" : undefined}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => {
                setSearchParams({ tab: "questions" });
              }}
              className={`px-3 py-2 text-sm font-medium ${
                tab === "questions"
                  ? "border-b-2 border-accent text-text"
                  : "text-text-secondary hover:text-text"
              }`}
              aria-current={tab === "questions" ? "page" : undefined}
            >
              Signal questions
            </button>
          </div>

          {tab === "overview" ? <OverviewTab service={service} /> : <QuestionsTab serviceId={id} />}
        </>
      )}
    </div>
  );
}
