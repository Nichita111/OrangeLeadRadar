import { useRef, useState } from "react";
import { useSearchParams } from "react-router";

import type { Schemas } from "../../../api/contract";
import {
  useProspects,
  type Band,
  type ProspectRow,
  type ProspectSort,
  type Standing,
} from "../../../api/prospectsAndEvidence";
import { useBandThresholds, useIndustries, useMarkets } from "../../../api/referenceData";
import { Button, ButtonLink } from "../../../components/Button";
import { Select, Input } from "../../../components/controls";
import { Skeleton } from "../../../components/Skeleton";
import { countryName, enumLabel } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { RelativeTime } from "../../../shell/RelativeTime";
import { DataView } from "../../../shell/states/DataView";
import { WithService } from "../../../shell/WithService";
import { BandChip } from "../BandChip";
import { TopSignals } from "../TopSignals";
import { ProspectDrawer } from "./ProspectDrawer";

const COLUMNS = [
  "#",
  "Account",
  "Band",
  "Priority",
  "Fit",
  "Intent",
  "Top signals",
  "Signals",
  "Last refresh",
];
const BANDS: Band[] = ["HOT", "WARM", "COLD"];
const STANDINGS: Standing[] = ["RANKED", "BELOW_FIT", "DISQUALIFIED", "CUSTOMER"];
const SORTS: { value: ProspectSort; label: string }[] = [
  { value: "priority", label: "Priority" },
  { value: "intent", label: "Intent" },
  { value: "fit", label: "Fit" },
  { value: "name", label: "Name" },
  { value: "last_refreshed", label: "Last refresh" },
];
const SKELETON_ROWS = [0, 1, 2, 3, 4];

const LABEL = "flex flex-col gap-1 text-hint text-text-tertiary";

function isStanding(value: string | null): value is Standing {
  return STANDINGS.some((standing) => standing === value);
}

function isSort(value: string | null): value is ProspectSort {
  return SORTS.some((option) => option.value === value);
}

function isBand(value: string | null): value is Band {
  return BANDS.some((band) => band === value);
}

/** FR-064: the one-line reason of a row that is not ranked. */
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

/** S-PRO: Prospects, `/prospects`, any signed-in user. WF-12, WF-25. Renders `API-39` as it comes. */
export function ProspectsScreen() {
  return (
    <>
      <PageHeader
        title="Prospects"
        lead="Accounts ranked by Priority for the selected service. Select a row to see why it is on the list."
      />
      <WithService>{(service) => <ProspectsList service={service} />}</WithService>
    </>
  );
}

function ProspectsList({ service }: { service: Schemas["Service"] }) {
  const [params, setParams] = useSearchParams();
  const industries = useIndustries();
  const markets = useMarkets();
  const thresholds = useBandThresholds(service.id);
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

  const prospects = useProspects(service.id, {
    page,
    standing,
    band,
    country_code: country,
    industry,
    q: search,
    sort,
  });

  /** FR-014: every filter, the sort and the page live in the URL; a change of filter returns to the first page. */
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

  const data = prospects.data;
  const pageCount = data === undefined ? 1 : Math.max(1, Math.ceil(data.total / data.page_size));
  const counts = data?.band_counts ?? {};
  const allCount = BANDS.reduce((sum, name) => sum + (counts[name] ?? 0), 0);

  return (
    <>
      <div className="flex flex-wrap items-end gap-3">
        <label className={LABEL}>
          Status
          <Select
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
                {enumLabel(value)}
              </option>
            ))}
          </Select>
        </label>
        {standing === "RANKED" && (
          <div role="group" aria-label="Band" className="flex gap-1">
            {[
              { value: undefined, label: "All", count: allCount },
              ...BANDS.map((name) => ({
                value: name,
                label: enumLabel(name),
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
        <label className={LABEL}>
          Country
          <Select
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
          </Select>
        </label>
        <label className={LABEL}>
          Industry
          <Select
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
          </Select>
        </label>
        <div className={LABEL}>
          <label htmlFor="prospects-search">Search</label>
          <Input
            id="prospects-search"
            type="search"
            value={search}
            onChange={(event) => {
              update({ q: event.target.value });
            }}
          />
        </div>
        <label className={LABEL}>
          Sort by
          <Select
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
          </Select>
        </label>
      </div>

      <DataView
        query={prospects}
        isEmpty={(result) => result.items.length === 0}
        skeleton={
          <div className="flex flex-col gap-2" aria-busy="true">
            {SKELETON_ROWS.map((row) => (
              <Skeleton key={row} className="h-12 w-full" />
            ))}
          </div>
        }
        empty={
          service.active_version === null
            ? {
                message: "Accounts appear after their first refresh.",
                action: <ButtonLink to="/accounts">Go to Accounts</ButtonLink>,
              }
            : {
                message: "No accounts match these filters.",
                action: (
                  <Button
                    onClick={() => {
                      setParams({});
                    }}
                  >
                    Clear filters
                  </Button>
                ),
              }
        }
      >
        {(result) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <caption className="sr-only">Prospects</caption>
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
                {result.items.map((row) => (
                  <tr key={row.account.id} className="border-b border-border last:border-b-0">
                    <td className="num px-4 py-3">{row.rank}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        className="font-medium hover:underline"
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
                      <p className="m-0 text-hint text-text-tertiary">
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
                    </td>
                    <td className="px-4 py-3">
                      <BandChip standing={row.standing} band={row.band} />
                    </td>
                    <td className="num px-4 py-3">{row.priority}</td>
                    <td className="num px-4 py-3">{row.fit}</td>
                    <td className="num px-4 py-3">{row.intent}</td>
                    <td className="px-4 py-3">
                      {reasonOf(row) ?? <TopSignals signals={row.top_signals} />}
                    </td>
                    <td className="num px-4 py-3">{row.finding_count}</td>
                    <td className="px-4 py-3 text-text-secondary">
                      {row.last_refreshed_at === null ? (
                        "Never"
                      ) : (
                        <RelativeTime at={row.last_refreshed_at} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>

      {data !== undefined && data.total > data.page_size && (
        <div className="flex items-center gap-3 text-text-secondary">
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

      {standing === "RANKED" && thresholds.data != null && (
        <p className="m-0 text-hint text-text-tertiary">
          {`Hot: Priority ${String(thresholds.data.hot_threshold)} or more. Warm: ${String(thresholds.data.warm_threshold)} to ${String(thresholds.data.hot_threshold - 1)}. Cold: below ${String(thresholds.data.warm_threshold)}.`}
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
    </>
  );
}
