/**
 * [Services](/features/service-configuration.md#services). Route `/services`, Admin only. WF-02.
 */
import { ArrowCounterClockwiseIcon, ProhibitIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useServices, useUpdateService, type Service } from "../../../api/services";
import { Button } from "../../../components/Button";
import { Chip } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/Dialog";
import { EmptyState, ErrorState, SkeletonRows, UnavailableState } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { useToast } from "../../../components/Toast";
import { titleCaseEnum } from "../../../shell/formatting";
import { NewServiceDialog } from "./NewServiceDialog";

const COLUMN_COUNT = 6;

export function ServicesScreen() {
  const { data: services, isLoading, isError, error, refetch } = useServices();
  const { showToast } = useToast();
  const updateService = useUpdateService();

  const [showNewService, setShowNewService] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<Service | null>(null);

  const handleReactivate = (service: Service) => {
    updateService.mutate(
      { id: service.id, body: { status: "ACTIVE" } },
      {
        onSuccess: () => {
          showToast(`${service.name} was reactivated.`);
        },
      },
    );
  };

  const handleConfirmDeactivate = () => {
    if (deactivateTarget === null) {
      return;
    }
    updateService.mutate(
      { id: deactivateTarget.id, body: { status: "INACTIVE" } },
      {
        onSuccess: () => {
          showToast(`${deactivateTarget.name} was deactivated.`);
          setDeactivateTarget(null);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold text-text">Services</h1>
          <p className="mt-1 text-sm text-text-secondary">
            Define the services accounts are scored for, their signal questions and their scoring.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            setShowNewService(true);
          }}
        >
          New service
        </Button>
      </div>

      <Table caption="Services">
        <TableHead>
          <TableRow>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Code</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Scoring</TableHeaderCell>
            <TableHeaderCell>Questions</TableHeaderCell>
            <TableHeaderCell>
              <span className="sr-only">Actions</span>
            </TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {isLoading && <SkeletonRows rows={3} columns={COLUMN_COUNT} />}
          {!isLoading && isError && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                {error instanceof ApiError && (error.status === 503 || error.status === 429) ? (
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
                )}
              </TableCell>
            </TableRow>
          )}
          {!isLoading && !isError && services !== undefined && services.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <EmptyState
                  message="No services yet. Create the first one to start scoring accounts."
                  actionLabel="New service"
                  onAction={() => {
                    setShowNewService(true);
                  }}
                />
              </TableCell>
            </TableRow>
          )}
          {!isLoading &&
            !isError &&
            services !== undefined &&
            services.map((service) => (
              <TableRow key={service.id}>
                <TableCell>
                  <Link
                    to={`/services/${service.id}`}
                    className="font-medium text-text hover:underline"
                  >
                    {service.name}
                  </Link>
                  <p className="mt-0.5 max-w-md text-[12.5px] text-text-secondary">
                    {service.description}
                  </p>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-[13px]">{service.code}</span>
                </TableCell>
                <TableCell>
                  <Chip tone={service.status === "ACTIVE" ? "positive" : "neutral"}>
                    {titleCaseEnum(service.status)}
                  </Chip>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1.5">
                    {service.active_version !== null && (
                      <Chip tone="positive">{`v${String(service.active_version)} active`}</Chip>
                    )}
                    {service.draft_version !== null && (
                      <Chip tone="caution">{`draft v${String(service.draft_version)}`}</Chip>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <span className="font-mono text-[13px]">{service.question_count}</span>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Link to={`/services/${service.id}?tab=questions`}>
                      <Button variant="ghost" size="small" type="button">
                        Questions
                      </Button>
                    </Link>
                    {service.status === "ACTIVE" ? (
                      <Button
                        variant="ghost"
                        size="small"
                        aria-label={`Deactivate ${service.name}`}
                        title="Deactivate"
                        onClick={() => {
                          setDeactivateTarget(service);
                        }}
                      >
                        <ProhibitIcon size={16} aria-hidden="true" />
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="small"
                        aria-label={`Reactivate ${service.name}`}
                        title="Reactivate"
                        onClick={() => {
                          handleReactivate(service);
                        }}
                      >
                        <ArrowCounterClockwiseIcon size={16} aria-hidden="true" />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>

      <NewServiceDialog
        open={showNewService}
        onOpenChange={setShowNewService}
        onCreated={showToast}
      />

      <ConfirmDialog
        open={deactivateTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeactivateTarget(null);
          }
        }}
        title="Deactivate service"
        description={
          <>
            {deactivateTarget?.name} will stop being refreshed, scored and listed in Prospects. Its
            data is kept and it can be reactivated later.
          </>
        }
        confirmLabel="Deactivate service"
        onConfirm={handleConfirmDeactivate}
        confirmPending={updateService.isPending}
      />
    </div>
  );
}
