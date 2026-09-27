import { useState } from "react";

import { useAcknowledgeAlert, useAlerts, type AlertView } from "../../../api/alerts";
import { Button, ButtonLink } from "../../../components/Button";
import { Skeleton } from "../../../components/Skeleton";
import { enumLabel, strengthLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";

/** What happened, in words (`FR-076`). */
function headline(alert: AlertView): string {
  if (alert.finding !== null) {
    return `New ${strengthLabel(alert.finding.strength).toLowerCase()} signal: ${alert.finding.question_text}`;
  }
  if (alert.band_change !== null) {
    const from = alert.band_change.from === null ? "no band" : enumLabel(alert.band_change.from);
    const to = alert.band_change.to === null ? "no band" : enumLabel(alert.band_change.to);
    return `Moved from ${from} to ${to}`;
  }
  return enumLabel(alert.kind);
}

/** S-PRO-06: Alerts, `/alerts`, any signed-in user. FR-076, FR-077, FR-135, FR-136. */
export function AlertsScreen() {
  return (
    <>
      <PageHeader
        title="Alerts"
        lead="Strong new signals and band rises for the selected service, newest first."
      />
      <WithService>{(service) => <AlertList serviceId={service.id} />}</WithService>
    </>
  );
}

function AlertList({ serviceId }: { serviceId: string }) {
  const [unread, setUnread] = useState(true);
  const alerts = useAlerts(serviceId, unread);
  const unreadCount = useAlerts(serviceId, true).data?.total;
  const acknowledge = useAcknowledgeAlert();

  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label="Show" className="flex gap-1">
        <Button
          size="small"
          variant={unread ? "primary" : "secondary"}
          aria-pressed={unread}
          onClick={() => {
            setUnread(true);
          }}
        >
          Unread{unreadCount === undefined ? "" : ` ${String(unreadCount)}`}
        </Button>
        <Button
          size="small"
          variant={unread ? "secondary" : "primary"}
          aria-pressed={!unread}
          onClick={() => {
            setUnread(false);
          }}
        >
          All
        </Button>
      </div>
      <DataView
        query={alerts}
        isEmpty={(page) => page.items.length === 0}
        skeleton={<Skeleton className="h-48 w-full" />}
        empty={{
          message: unread
            ? "You are all caught up. New alerts appear here after a refresh finds a strong signal or an account moves up a band."
            : "No alert yet. Alerts appear here after a refresh finds a strong signal or an account moves up a band.",
          action: null,
        }}
      >
        {(page) => (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {page.items.map((alert) => {
              const read = alert.acknowledged_at !== null;
              return (
                <li
                  key={alert.id}
                  className={`flex items-start justify-between gap-4 rounded-card border border-border bg-surface p-4 ${
                    read ? "opacity-60" : "border-l-4 border-l-accent"
                  }`}
                >
                  <div className="flex min-w-0 flex-col gap-1">
                    <span className="font-semibold">{alert.account.name}</span>
                    <span>{headline(alert)}</span>
                    {alert.finding !== null && (
                      <blockquote className="m-0 border-l-2 border-border pl-3 text-text-secondary">
                        &ldquo;{alert.finding.quote}&rdquo;
                      </blockquote>
                    )}
                    <span className="text-hint text-text-tertiary">
                      <RelativeTime at={alert.created_at} />
                      {read && alert.acknowledged_at !== null && (
                        <>
                          {" · Read by "}
                          {alert.acknowledged_by_name ?? "someone"}{" "}
                          <RelativeTime at={alert.acknowledged_at} />
                        </>
                      )}
                    </span>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <ButtonLink size="small" to={`/accounts/${alert.account.id}`}>
                      Open
                    </ButtonLink>
                    {!read && (
                      <Button
                        size="small"
                        variant="ghost"
                        disabled={acknowledge.isPending}
                        onClick={() => {
                          acknowledge.mutate(alert.id);
                        }}
                      >
                        Mark read
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </DataView>
    </div>
  );
}
