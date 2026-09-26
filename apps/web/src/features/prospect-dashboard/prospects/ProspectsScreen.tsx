/**
 * [Prospects](/features/prospect-dashboard.md#prospects). Route `/prospects`, any signed-in
 * user. WF-12, WF-25. Renders `API-39` as it comes: the api ranks, filters and counts.
 */
import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useIndustries, useMarkets } from "../../../api/industriesAndMarkets";
import {
  useProspects,
  type Band,
  type ProspectRow,
  type ProspectSort,
  type Standing,
} from "../../../api/prospects";
import { useActiveScoringSettings } from "../../../api/scoring";
import { Button } from "../../../components/Button";
import { BandChip } from "../../../components/score/BandChip";
import { EmptyState, QueryErrorState, SkeletonRows } from "../../../components/States";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../../../components/Table";
import { countryName } from "../../../shell/countries";
import {
  formatAbsoluteDateTime,
  formatRelativeDate,
  strengthLabel,
} from "../../../shell/formatting";
import { BAND_LABELS, STANDING_LABELS } from "../../../shell/labels";
import { useServiceSelection } from "../../../shell/selected-service";
import { ProspectDrawer } from "./ProspectDrawer";

const COLUMN_COUNT = 9;
const BANDS: Band[] = ["HOT", "WARM", "COLD"];
const STANDINGS: Standing[] = ["RANKED", "BELOW_FIT", "DISQUALIFIED", "CUSTOMER"];
const SORTS: { value: ProspectSort; label: string }[] = [
  { value: "priority", label: "Priority" },
  { value: "intent", label: "Intent" },
  { value: "fit", label: "Fit" },
  { value: "name", label: "Name" },
  { value: "last_refreshed", label: "Last refresh" },
];

const CONTROL = "rounded-control border border-border bg-surface px-3 text-sm text-text";

function isStanding(value: string | null): value is Standing {
  return STANDINGS.some((standing) => standing === value);
}

function isSort(value: string | null): value is ProspectSort {
  return SORTS.some((option) => option.value === value);
}

function isBand(value: string | null): value is Band {
  return BANDS.some((band) => band === value);
}

/** `FR-064`: the one-line reason of a row that is not ranked. */
function reasonOf(row: ProspectRow): string | null {
  if (row.reason === null) {
    return null;
  }
  switch (row.standing) {
    case "BELOW_FIT":
      return `Fit below the minimum of ${String(row.reason.min_fit)}`;
    case "DISQUALIFIED":
      return `Excluded by ${(row.reason.disqualifier_labels ?? []).join(", ")}`;
    case "CUSTOMER":
      return `Marked as a customer by ${row.reason.customer_marked_by_name ?? "a user"}`;
    case "RANKED":
      return null;
  }
}

export function ProspectsScreen() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const selection = useServiceSelection();
  const { isLoading: servicesLoading, service } = selection;
  const industries = useIndustries();
  const markets = useMarkets();
  const settings = useActiveScoringSettings(service?.id);
  const [openRow, setOpenRow] = useState<ProspectRow | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const standingParam = params.get("standing");
  const standing = isStanding(standingParam) ? standingParam : "RANKED";
  const bandParam = params.get("band");
  const band = isBand(bandParam) ? bandParam : undefined;
  const country = params.get("country_code") ?? "";
  const industry = params.get("industry") ?? "";
  const search = params.get("q") ?? "";
  const sortParam = params.get("sort");
  const sort = isSort(sortParam) ? sortParam : "priority";
  const pageNumber = Number(params.get("page"));
  const page = Number.isInteger(pageNumber) && pageNumber >= 1 ? pageNumber : 1;

  const prospects = useProspects(service?.id, {
    page,
    standing,
    band,
    country_code: country,
    industry,
    q: search,
    sort,
  });

  /** `FR-014`: every filter, the sort and the page live in the URL; a change of filter returns
   * to the first page. */
  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [name, value] of Object.entries(patch)) {
      if (value === "") {
        next.delete(name);
      } else {
        next.set(name, value);
      }
    }
    if (!("page" in patch)) {
      next.delete("page");
    }
    setParams(next);
  };

  const countries = [
    ...new Set(
      (markets.data ?? [])
        .filter((market) => market.status === "ACTIVE")
        .flatMap((market) => market.country_codes),
    ),
  ];
  const industryLabels = new Map((industries.data ?? []).map((item) => [item.code, item.label]));
  const activeIndustries = (industries.data ?? []).filter((item) => item.status === "ACTIVE");

  const header = (
    <div>
      <h1 className="text-[24px] font-semibold text-text">Prospects</h1>
      <p className="mt-1 text-sm text-text-secondary">
        Accounts ranked by Priority for the selected service. Select a row to see why it is on the
        list.
      </p>
    </div>
  );

  if (selection.error !== null) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <QueryErrorState error={selection.error} onRetry={selection.refetch} />
      </div>
    );
  }
  if (!servicesLoading && service === null) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <p className="text-sm text-text-secondary">There is no active service yet.</p>
      </div>
    );
  }

  const page_ = prospects.data;
  const pageCount = page_ === undefined ? 1 : Math.max(1, Math.ceil(page_.total / page_.page_size));
  const counts = page_?.band_counts ?? {};
  const allCount = BANDS.reduce((sum, name) => sum + (counts[name] ?? 0), 0);

  return (
    <div className="flex flex-col gap-6">
      {header}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Status
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={standing}
            onChange={(event) => {
              update({
                standing: event.target.value === "RANKED" ? "" : event.target.value,
                band: "",
              });
            }}
          >
            {STANDINGS.map((value) => (
              <option key={value} value={value}>
                {STANDING_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        {standing === "RANKED" && (
          <div role="group" aria-label="Band" className="flex gap-1">
            {[
              { value: undefined, label: "All", count: allCount },
              ...BANDS.map((name) => ({
                value: name,
                label: BAND_LABELS[name],
                count: counts[name] ?? 0,
              })),
            ].map((option) => (
              <Button
                key={option.label}
                size="small"
                variant={band === option.value ? "primary" : "secondary"}
                aria-pressed={band === option.value}
                onClick={() => {
                  update({ band: option.value ?? "" });
                }}
              >
                {`${option.label} ${String(option.count)}`}
              </Button>
            ))}
          </div>
        )}
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Country
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={country}
            onChange={(event) => {
              update({ country_code: event.target.value });
            }}
          >
            <option value="">All countries</option>
            {countries.map((code) => (
              <option key={code} value={code}>
                {countryName(code)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Industry
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={industry}
            onChange={(event) => {
              update({ industry: event.target.value });
            }}
          >
            <option value="">All industries</option>
            {activeIndustries.map((item) => (
              <option key={item.code} value={item.code}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Search
          <input
            type="search"
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={search}
            onChange={(event) => {
              update({ q: event.target.value });
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-[12.5px] text-text-tertiary">
          Sort by
          <select
            className={CONTROL}
            style={{ height: "var(--ctl-input)" }}
            value={sort}
            onChange={(event) => {
              update({ sort: event.target.value === "priority" ? "" : event.target.value });
            }}
          >
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Table caption="Prospects">
        <TableHead>
          <TableRow>
            <TableHeaderCell>#</TableHeaderCell>
            <TableHeaderCell>Account</TableHeaderCell>
            <TableHeaderCell>Band</TableHeaderCell>
            <TableHeaderCell>Priority</TableHeaderCell>
            <TableHeaderCell>Fit</TableHeaderCell>
            <TableHeaderCell>Intent</TableHeaderCell>
            <TableHeaderCell>Top signals</TableHeaderCell>
            <TableHeaderCell>Signals</TableHeaderCell>
            <TableHeaderCell>Last refresh</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {(servicesLoading || prospects.isLoading) && (
            <SkeletonRows rows={5} columns={COLUMN_COUNT} />
          )}
          {prospects.isError && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                <QueryErrorState error={prospects.error} onRetry={() => void prospects.refetch()} />
              </TableCell>
            </TableRow>
          )}
          {page_ !== undefined && page_.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT}>
                {service?.active_version === null ? (
                  <EmptyState
                    message="Accounts appear after their first refresh."
                    actionLabel="Go to Accounts"
                    onAction={() => {
                      void navigate("/accounts");
                    }}
                  />
                ) : (
                  <EmptyState
                    message="No accounts match these filters."
                    actionLabel="Clear filters"
                    onAction={() => {
                      setParams({});
                    }}
                  />
                )}
              </TableCell>
            </TableRow>
          )}
          {page_?.items.map((row) => (
            <TableRow key={row.account.id}>
              <TableCell>{row.rank}</TableCell>
              <TableCell>
                <button
                  type="button"
                  className="font-medium text-text hover:underline"
                  onClick={(event) => {
                    returnFocusRef.current = event.currentTarget;
                    setOpenRow(row);
                  }}
                >
                  {row.account.name}
                </button>
                {row.unread_alerts > 0 && (
                  <span
                    role="img"
                    aria-label={`${String(row.unread_alerts)} unread alerts`}
                    title={`${String(row.unread_alerts)} unread alerts`}
                    className="ml-2 inline-block size-2 rounded-full bg-accent align-middle"
                  />
                )}
                <p className="text-[12.5px] text-text-tertiary">
                  {[
                    row.account.country_code === null
                      ? null
                      : countryName(row.account.country_code),
                    row.account.industry === null
                      ? null
                      : (industryLabels.get(row.account.industry) ?? row.account.industry),
                  ]
                    .filter((part) => part !== null)
                    .join(", ")}
                </p>
              </TableCell>
              <TableCell>
                <BandChip standing={row.standing} band={row.band} />
              </TableCell>
              <TableCell>
                <span className="font-mono">{row.priority}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">{row.fit}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">{row.intent}</span>
              </TableCell>
              <TableCell>
                {reasonOf(row) ?? (
                  <ul className="flex flex-col gap-0.5 text-[12.5px]">
                    {row.top_signals.map((signal) => (
                      <li key={signal.question_key}>
                        {signal.question_text}, {strengthLabel(signal.strength)},{" "}
                        <span title={formatAbsoluteDateTime(signal.observed_at)}>
                          {formatRelativeDate(signal.observed_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </TableCell>
              <TableCell>
                <span className="font-mono">{row.finding_count}</span>
              </TableCell>
              <TableCell>
                {row.last_refreshed_at === null ? (
                  "Never"
                ) : (
                  <span title={formatAbsoluteDateTime(row.last_refreshed_at)}>
                    {formatRelativeDate(row.last_refreshed_at)}
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {page_ !== undefined && page_.total > page_.page_size && (
        <div className="flex items-center gap-3 text-sm text-text-secondary">
          <Button
            size="small"
            disabled={page <= 1}
            onClick={() => {
              update({ page: String(page - 1) });
            }}
          >
            Previous
          </Button>
          <span>{`Page ${String(page)} of ${String(pageCount)}`}</span>
          <Button
            size="small"
            disabled={page >= pageCount}
            onClick={() => {
              update({ page: String(page + 1) });
            }}
          >
            Next
          </Button>
        </div>
      )}

      {standing === "RANKED" && settings.data != null && (
        <p className="text-[12.5px] text-text-tertiary">
          {`Hot: Priority ${String(settings.data.hot_threshold)} or more. Warm: ${String(settings.data.warm_threshold)} to ${String(settings.data.hot_threshold - 1)}. Cold: below ${String(settings.data.warm_threshold)}.`}
        </p>
      )}

      {openRow !== null && (
        <ProspectDrawer
          row={openRow}
          returnFocusRef={returnFocusRef}
          onClose={() => {
            setOpenRow(null);
          }}
        />
      )}
    </div>
  );
}
