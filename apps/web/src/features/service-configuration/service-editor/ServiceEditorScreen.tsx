import { useParams, useSearchParams } from "react-router";

import { useService } from "../../../api/servicesAndQuestions";
import { Skeleton } from "../../../components/Skeleton";
import { DataView } from "../../../shell/states/DataView";
import { OverviewTab } from "./OverviewTab";
import { QuestionsTab } from "./QuestionsTab";
import { ServiceTabs } from "./ServiceTabs";

/**
 * [Service editor](/features/service-configuration.md#service-editor). Route `/services/:id`,
 * Admin only. Overview and Signal questions live here; Scoring is a link to the separate
 * [Scoring settings](/features/service-configuration.md#scoring-settings) route (G2).
 */
export function ServiceEditorScreen() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "questions" ? "questions" : "overview";
  const service = useService(id);

  if (id === undefined) {
    return null;
  }

  return (
    <DataView
      query={service}
      isEmpty={() => false}
      skeleton={<Skeleton className="h-64 w-full" />}
      empty={{ message: "", action: null }}
    >
      {(data) => (
        <div className="flex flex-col gap-6">
          <h1 className="m-0 text-title font-semibold">{data.name}</h1>
          <ServiceTabs serviceId={id} active={tab} />
          {tab === "overview" ? <OverviewTab service={data} /> : <QuestionsTab serviceId={id} />}
        </div>
      )}
    </DataView>
  );
}
