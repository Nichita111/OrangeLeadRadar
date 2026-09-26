import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { requestUrl, services } from "../fixtures";
import { renderScreen } from "../renderScreen";
import { ProspectsScreen } from "./ProspectsScreen";

function renderProspects(url = "/prospects", overrides = {}) {
  return renderScreen("/prospects", <ProspectsScreen />, url, overrides);
}

function requestedUrls(spy: ReturnType<typeof renderProspects>): string[] {
  return spy.mock.calls.map(([input]) => requestUrl(input));
}

describe("ProspectsScreen", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("FR-062, FR-063: lists the api's ranking with rank, band, figures, top signals and unread marker", async () => {
    renderProspects();

    await screen.findByRole("button", { name: "DHL Group" });
    const [, dhlRow, lhRow] = screen.getAllByRole("row");
    const dhl = within(dhlRow as HTMLElement);
    expect(dhl.getByText("1")).toBeInTheDocument();
    expect(dhl.getByRole("button", { name: "DHL Group" })).toBeInTheDocument();
    expect(dhl.getByText("Germany, Logistics and transport")).toBeInTheDocument();
    expect(dhl.getByText("Hot")).toBeInTheDocument();
    expect(dhl.getByText("78")).toBeInTheDocument();
    expect(dhl.getByText(/AI and automation projects/)).toBeInTheDocument();
    expect(dhl.getByRole("img", { name: "2 unread alerts" })).toBeInTheDocument();
    const lufthansa = within(lhRow as HTMLElement);
    expect(lufthansa.getByRole("button", { name: "Lufthansa Group" })).toBeInTheDocument();
    expect(lufthansa.getByText("Warm")).toBeInTheDocument();
    expect(lufthansa.queryByRole("img", { name: /unread/ })).not.toBeInTheDocument();
  });

  it("FR-014, FR-063: choosing Hot and a country puts them in the URL and in the API-39 query", async () => {
    const spy = renderProspects();
    await screen.findByRole("button", { name: "DHL Group" });

    fireEvent.click(screen.getByRole("button", { name: /^Hot/ }));
    fireEvent.change(screen.getByLabelText("Country"), { target: { value: "DE" } });

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("band=HOT");
    });
    expect(screen.getByTestId("location")).toHaveTextContent("country_code=DE");
    await waitFor(() => {
      expect(
        requestedUrls(spy).some(
          (url) =>
            url.includes("/prospects?") &&
            url.includes("band=HOT") &&
            url.includes("country_code=DE"),
        ),
      ).toBe(true);
    });
  });

  it("FR-129, FR-117: shows band counts with All first and the legend from the active settings", async () => {
    renderProspects();

    await screen.findByRole("button", { name: "DHL Group" });
    const all = screen.getByRole("button", { name: /^All/ });
    const bands = screen.getAllByRole("button", { name: /^(All|Hot|Warm|Cold) \d/ });
    expect(bands[0]).toBe(all);
    expect(all).toHaveTextContent("All 2");
    expect(screen.getByRole("button", { name: /^Hot/ })).toHaveTextContent("Hot 1");
    await waitFor(() => {
      expect(screen.getByText(/Hot: Priority 75 or more/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Warm: 40 to 74/)).toBeInTheDocument();
    expect(screen.getByText(/Cold: below 40/)).toBeInTheDocument();
  });

  it("FR-064: status Excluded lists rows with the reason and no rank or band", async () => {
    renderProspects("/prospects?standing=DISQUALIFIED");

    const row = (await screen.findByRole("button", { name: "Aerofrance" })).closest("tr");
    const within_ = within(row as HTMLElement);
    expect(within_.getByText("Excluded by Outside DACH")).toBeInTheDocument();
    expect(within_.queryByText("Hot")).not.toBeInTheDocument();
    expect(within_.queryByText("Warm")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Hot/ })).not.toBeInTheDocument();
  });

  it("FR-065: an empty result is the filtered-empty state, and no active version says accounts come after the first refresh", async () => {
    renderProspects("/prospects?standing=BELOW_FIT");
    expect(await screen.findByText("No accounts match these filters.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
    vi.unstubAllGlobals();

    renderProspects("/prospects", {
      routes: {
        "GET /services": () =>
          new Response(
            JSON.stringify(services.map((item) => ({ ...item, active_version: null }))),
            { status: 200 },
          ),
        "GET /services/svc-1/prospects": () =>
          new Response(
            JSON.stringify({ items: [], page: 1, page_size: 25, total: 0, band_counts: {} }),
            { status: 200 },
          ),
      },
    });
    expect(await screen.findByText(/appear after their first refresh/)).toBeInTheDocument();
  });

  it("FR-130: selecting a row opens the drawer with the meanings and the link; Escape closes it and returns focus", async () => {
    renderProspects();
    const trigger = await screen.findByRole("button", { name: "DHL Group" });

    fireEvent.click(trigger);

    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByText(/Fit, how well it matches/)).toBeInTheDocument();
    expect(within(drawer).getByText(/Intent, recent signals/)).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "Open full explanation" })).toHaveAttribute(
      "href",
      "/accounts/acc-dhl",
    );
    fireEvent.keyDown(drawer, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(trigger).toHaveFocus();
  });

  it("R-4: an unknown sort and a bad page in the URL are not sent to API-39", async () => {
    const spy = renderProspects("/prospects?sort=foo&page=abc");
    await screen.findByRole("button", { name: "DHL Group" });

    const listUrl = requestedUrls(spy).find((url) => url.includes("/prospects?")) ?? "";
    expect(listUrl).toContain("sort=priority");
    expect(listUrl).toContain("page=1");
  });
});
