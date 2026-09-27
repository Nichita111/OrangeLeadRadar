import { PlusIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router";

import { useServices, useUpdateService } from "../../../api/servicesAndQuestions";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { RowMenu } from "../../../components/RowMenu";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { PageHeader } from "../../../shell/PageHeader";
import { DataView } from "../../../shell/states/DataView";
import { NewServiceDialog } from "./NewServiceDialog";

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-14 w-full" />
      ))}
    </div>
  );
}

const COLUMNS = ["Service", "Status", "Scoring", "Questions", "Actions"];
const DEACTIVATE_NOTE = "will stop being refreshed, scored and listed; its data is kept.";

/** FL-01, FR-018 to FR-020, FR-149, S-CFG-01: list, create, deactivate and reactivate services. */
export function ServicesScreen() {
  const services = useServices();

  return (
    <>
      <PageHeader
        title="Services"
        lead="Define the services accounts are scored for, their signal questions and their scoring."
        action={
          <NewServiceDialog
            trigger={
              <Button variant="primary">
                <PlusIcon size={16} aria-hidden />
                New service
              </Button>
            }
          />
        }
      />
      <DataView
        query={services}
        isEmpty={(rows) => rows.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No services yet. New service creates the first one.",
          action: <NewServiceDialog trigger={<Button variant="secondary">New service</Button>} />,
        }}
      >
        {(rows) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {COLUMNS.map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((service) => (
                  <ServiceRow key={service.id} service={service} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
    </>
  );
}

function ServiceRow({ service }: { service: Schemas["Service"] }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const update = useUpdateService();
  const { notify } = useToast();
  const isActive = service.status === "ACTIVE";

  return (
    <>
      <tr className="border-b border-border last:border-b-0">
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <Link to={`/services/${service.id}`} className="font-medium hover:underline">
              {service.name}
            </Link>
            <span className="num text-hint text-text-tertiary">{service.code}</span>
          </div>
          <p className="m-0 mt-0.5 max-w-md text-hint text-text-secondary">{service.description}</p>
        </td>
        <td className="px-4 py-3">
          <Chip tone={isActive ? "positive" : "neutral"}>{isActive ? "Active" : "Inactive"}</Chip>
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1.5">
            {service.active_version !== null && (
              <Chip tone="positive">{`v${String(service.active_version)}`}</Chip>
            )}
            {service.draft_version !== null && (
              <Chip tone="caution">{`draft v${String(service.draft_version)}`}</Chip>
            )}
            <Link to={`/services/${service.id}/scoring`} className="text-hint hover:underline">
              Scoring
            </Link>
          </div>
        </td>
        <td className="px-4 py-3">
          <Link
            to={`/services/${service.id}?tab=questions`}
            className="num hover:underline"
          >{`${String(service.question_count)} questions`}</Link>
        </td>
        <td className="px-4 py-3">
          <RowMenu
            label={`Actions for ${service.name}`}
            items={[
              isActive
                ? {
                    label: "Deactivate",
                    onSelect: () => {
                      setConfirmOpen(true);
                    },
                  }
                : {
                    label: "Reactivate",
                    onSelect: () => {
                      update.mutate(
                        { id: service.id, body: { status: "ACTIVE" } },
                        {
                          onSuccess: () => {
                            notify("Service reactivated");
                          },
                        },
                      );
                    },
                  },
            ]}
          />
          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title="Deactivate service"
            description={`${service.name} ${DEACTIVATE_NOTE}`}
            confirmLabel="Deactivate service"
            onConfirm={() => {
              update.mutate(
                { id: service.id, body: { status: "INACTIVE" } },
                {
                  onSuccess: () => {
                    notify("Service deactivated");
                  },
                },
              );
            }}
          />
        </td>
      </tr>
      {update.isError && (
        <tr className="border-b border-border last:border-b-0">
          <td colSpan={COLUMNS.length} className="px-4 pb-3">
            <Callout kind="error">{update.error.message}</Callout>
          </td>
        </tr>
      )}
    </>
  );
}
