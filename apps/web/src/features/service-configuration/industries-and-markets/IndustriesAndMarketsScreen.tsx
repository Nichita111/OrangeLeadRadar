import { PlusIcon } from "@phosphor-icons/react";
import { useState } from "react";

import {
  useIndustries,
  useMarkets,
  useUpdateIndustry,
  useUpdateMarket,
} from "../../../api/industriesAndMarkets";
import type { Schemas } from "../../../api/contract";
import { Button } from "../../../components/Button";
import { Callout } from "../../../components/Callout";
import { Chip } from "../../../components/Chip";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { RowMenu } from "../../../components/RowMenu";
import { Skeleton } from "../../../components/Skeleton";
import { useToast } from "../../../components/Toast";
import { countryName } from "../../../shell/format";
import { PageHeader } from "../../../shell/PageHeader";
import { DataView } from "../../../shell/states/DataView";
import { IndustryDialog } from "./IndustryDialog";
import { MarketDialog } from "./MarketDialog";

function SkeletonRows() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-12 w-full" />
      ))}
    </div>
  );
}

const RETIRE_NOTE =
  "will leave every picker; accounts and saved scoring versions that already use it keep it.";
const RESTORE_NOTE = "will be offered in pickers again.";

/** FL-22, FR-154 to FR-156, S-CFG-07: create, rename, retire and restore industries and markets. */
export function IndustriesAndMarketsScreen() {
  return (
    <>
      <PageHeader
        title="Industries and markets"
        lead="Keep the industries and markets accounts and scoring criteria draw on, and retire the ones no longer offered."
      />
      <IndustriesSection />
      <MarketsSection />
    </>
  );
}

function IndustriesSection() {
  const industries = useIndustries();

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="m-0 text-section font-semibold">Industries</h2>
        <IndustryDialog
          trigger={
            <Button variant="primary">
              <PlusIcon size={16} aria-hidden />
              New industry
            </Button>
          }
        />
      </div>
      <DataView
        query={industries}
        isEmpty={(rows) => rows.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No industries yet. New industry creates the first one.",
          action: <IndustryDialog trigger={<Button variant="secondary">New industry</Button>} />,
        }}
      >
        {(rows) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {["Code", "Label", "Status", "Accounts", "Actions"].map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((industry) => (
                  <IndustryRow key={industry.code} industry={industry} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
    </section>
  );
}

function IndustryRow({ industry }: { industry: Schemas["Industry"] }) {
  const [renameOpen, setRenameOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const update = useUpdateIndustry();
  const { notify } = useToast();
  const isActive = industry.status === "ACTIVE";

  return (
    <>
      <tr className="border-b border-border last:border-b-0">
        <td className="num px-4 py-3 font-medium">{industry.code}</td>
        <td className="px-4 py-3">{industry.label}</td>
        <td className="px-4 py-3">
          <Chip tone={isActive ? "positive" : "neutral"}>{isActive ? "Active" : "Retired"}</Chip>
        </td>
        <td className="num px-4 py-3 text-text-secondary">{industry.account_count}</td>
        <td className="px-4 py-3">
          <RowMenu
            label={`Actions for ${industry.label}`}
            items={[
              {
                label: "Rename",
                onSelect: () => {
                  setRenameOpen(true);
                },
              },
              {
                label: isActive ? "Retire" : "Restore",
                onSelect: () => {
                  setConfirmOpen(true);
                },
              },
            ]}
          />
          <IndustryDialog industry={industry} open={renameOpen} onOpenChange={setRenameOpen} />
          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title={isActive ? "Retire industry" : "Restore industry"}
            description={`${industry.label} ${isActive ? RETIRE_NOTE : RESTORE_NOTE}`}
            confirmLabel={isActive ? "Retire industry" : "Restore industry"}
            onConfirm={() => {
              update.mutate(
                { code: industry.code, body: { status: isActive ? "INACTIVE" : "ACTIVE" } },
                {
                  onSuccess: () => {
                    notify(isActive ? "Industry retired" : "Industry restored");
                  },
                },
              );
            }}
          />
        </td>
      </tr>
      {update.isError && (
        <tr className="border-b border-border last:border-b-0">
          <td colSpan={5} className="px-4 pb-3">
            <Callout kind="error">{update.error.message}</Callout>
          </td>
        </tr>
      )}
    </>
  );
}

function MarketsSection() {
  const markets = useMarkets();

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="m-0 text-section font-semibold">Markets</h2>
        <MarketDialog
          trigger={
            <Button variant="primary">
              <PlusIcon size={16} aria-hidden />
              New market
            </Button>
          }
        />
      </div>
      <DataView
        query={markets}
        isEmpty={(rows) => rows.length === 0}
        skeleton={<SkeletonRows />}
        empty={{
          message: "No markets yet. New market creates the first one.",
          action: <MarketDialog trigger={<Button variant="secondary">New market</Button>} />,
        }}
      >
        {(rows) => (
          <div className="overflow-hidden rounded-card border border-border bg-surface">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-border text-hint text-text-tertiary">
                  {["Code", "Name", "Countries", "Status", "Actions"].map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((market) => (
                  <MarketRow key={market.code} market={market} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataView>
    </section>
  );
}

function MarketRow({ market }: { market: Schemas["Market"] }) {
  const [renameOpen, setRenameOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const update = useUpdateMarket();
  const { notify } = useToast();
  const isActive = market.status === "ACTIVE";

  return (
    <>
      <tr className="border-b border-border last:border-b-0">
        <td className="num px-4 py-3 font-medium">{market.code}</td>
        <td className="px-4 py-3">{market.name}</td>
        <td className="px-4 py-3 text-text-secondary">
          {market.country_codes.map((code) => countryName(code)).join(", ")}
        </td>
        <td className="px-4 py-3">
          <Chip tone={isActive ? "positive" : "neutral"}>{isActive ? "Active" : "Retired"}</Chip>
        </td>
        <td className="px-4 py-3">
          <RowMenu
            label={`Actions for ${market.name}`}
            items={[
              {
                label: "Rename",
                onSelect: () => {
                  setRenameOpen(true);
                },
              },
              {
                label: isActive ? "Retire" : "Restore",
                onSelect: () => {
                  setConfirmOpen(true);
                },
              },
            ]}
          />
          <MarketDialog market={market} open={renameOpen} onOpenChange={setRenameOpen} />
          <ConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            title={isActive ? "Retire market" : "Restore market"}
            description={`${market.name} ${isActive ? RETIRE_NOTE : RESTORE_NOTE}`}
            confirmLabel={isActive ? "Retire market" : "Restore market"}
            onConfirm={() => {
              update.mutate(
                { code: market.code, body: { status: isActive ? "INACTIVE" : "ACTIVE" } },
                {
                  onSuccess: () => {
                    notify(isActive ? "Market retired" : "Market restored");
                  },
                },
              );
            }}
          />
        </td>
      </tr>
      {update.isError && (
        <tr className="border-b border-border last:border-b-0">
          <td colSpan={5} className="px-4 pb-3">
            <Callout kind="error">{update.error.message}</Callout>
          </td>
        </tr>
      )}
    </>
  );
}
