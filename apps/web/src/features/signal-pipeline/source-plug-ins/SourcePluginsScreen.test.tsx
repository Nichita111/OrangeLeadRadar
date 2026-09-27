import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { errorEnvelope, errorResponse, olgaAdmin } from "../../../api/authenticationAndUsers.fixtures";
import type { Schemas } from "../../../api/contract";
import { renderApp, signedInAs } from "../../../testRender";
import { http, server } from "../../../testServer";

type SourcePlugin = Schemas["SourcePlugin"];

function plugin(overrides: Partial<SourcePlugin>): SourcePlugin {
  return {
    code: "GDELT",
    enabled: true,
    rate_limit_per_minute: 30,
    daily_quota: null,
    needs_key: false,
    key_configured: false,
    available: true,
    requests_today: 0,
    last_success_at: null,
    last_error: null,
    last_error_at: null,
    ...overrides,
  };
}

const gdelt = plugin({ code: "GDELT", rate_limit_per_minute: 10 });
const rss = plugin({ code: "RSS" });
const website = plugin({ code: "WEBSITE" });
const careers = plugin({ code: "CAREERS" });
const crunchbase = plugin({
  code: "CRUNCHBASE",
  needs_key: true,
  key_configured: true,
  last_success_at: "2026-09-26T12:00:00Z",
});
const newsapi = plugin({
  code: "NEWSAPI",
  needs_key: true,
  key_configured: false,
  available: false,
  last_error: "Timed out",
  last_error_at: "2026-09-26T10:00:00Z",
});
const serpapi = plugin({
  code: "SERPAPI",
  needs_key: true,
  key_configured: true,
  requests_today: 100,
  daily_quota: 100,
  available: false,
});
const SEVEN_PLUGINS = [gdelt, rss, website, careers, crunchbase, newsapi, serpapi];

function arrangePlugins(initial: SourcePlugin[]): SourcePlugin[] {
  const plugins = [...initial];
  server.use(http.get("/api/v1/source-plugins", ({ response }) => response(200).json(plugins)));
  return plugins;
}

async function openScreen() {
  signedInAs(olgaAdmin);
  const view = renderApp("/settings/source-plugins");
  await screen.findByRole("heading", { name: "Source plug-ins", level: 1 });
  return view;
}

function rowOf(name: string): Promise<HTMLElement> {
  return screen.findByRole("row", { name: new RegExp(name) });
}

describe("SourcePluginsScreen listing (FR-059)", () => {
  it("lists every plug-in with key need, key state, switch, availability, usage, limits, last success and last error", async () => {
    arrangePlugins(SEVEN_PLUGINS);
    await openScreen();

    const gdeltRow = await rowOf("GDELT");
    expect(within(gdeltRow).getByText("no")).toBeInTheDocument();
    // Needs no key ("—" in Key) and has no last error ("—" in Last error).
    expect(within(gdeltRow).getAllByText("—")).toHaveLength(2);
    expect(within(gdeltRow).getByRole("switch", { name: "Enabled, GDELT" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(within(gdeltRow).getByText("Available")).toBeInTheDocument();
    expect(within(gdeltRow).getByText("Never")).toBeInTheDocument();

    const crunchbaseRow = await rowOf("Crunchbase");
    expect(within(crunchbaseRow).getByText("yes")).toBeInTheDocument();
    expect(within(crunchbaseRow).getByText("set")).toBeInTheDocument();
    expect(within(crunchbaseRow).getByText(/ago$/)).toBeInTheDocument();

    const newsapiRow = await rowOf("NewsAPI");
    expect(within(newsapiRow).getByText("missing")).toBeInTheDocument();
    expect(within(newsapiRow).getByText("Timed out")).toBeInTheDocument();
  });
});

describe("SourcePluginsScreen empty state (G5, FR-059)", () => {
  it("names seeding and offers no button", async () => {
    arrangePlugins([]);
    await openScreen();
    expect(
      await screen.findByText("No plug-ins yet. They are created when the database is seeded."),
    ).toBeInTheDocument();
    expect(within(screen.getByRole("main")).queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("SourcePluginsScreen availability (FR-143, FR-060)", () => {
  it("says what each plug-in reads and shows Available, Switched off or Unavailable with its reason", async () => {
    arrangePlugins(SEVEN_PLUGINS);
    await openScreen();
    const gdeltRow = await rowOf("GDELT");
    expect(
      within(gdeltRow).getByText(
        "News articles worldwide that name the account, found through the GDELT Project",
      ),
    ).toBeInTheDocument();
    expect(
      within(await rowOf("NewsAPI")).getByText("Unavailable: key missing"),
    ).toBeInTheDocument();
    expect(
      within(await rowOf("SerpAPI")).getByText("Unavailable: daily quota reached"),
    ).toBeInTheDocument();
  });

  it("a plug-in whose key is missing says it stays unavailable until the key is set, even when enabled", async () => {
    arrangePlugins(SEVEN_PLUGINS);
    await openScreen();
    expect(
      within(await rowOf("NewsAPI")).getByText(
        "Stays unavailable until the key is set in the deployment's configuration.",
      ),
    ).toBeInTheDocument();
    expect(within(await rowOf("GDELT")).queryByText(/Stays unavailable/)).not.toBeInTheDocument();
    expect(
      within(await rowOf("Crunchbase")).queryByText(/Stays unavailable/),
    ).not.toBeInTheDocument();
  });
});

describe("SourcePluginsScreen switch (FR-061, FR-120)", () => {
  it("switching GDELT off sends PATCH {enabled: false}, shows the returned state and a toast; the switch is disabled while saving", async () => {
    const user = userEvent.setup();
    arrangePlugins(SEVEN_PLUGINS);
    const bodies: Schemas["SourcePluginUpdate"][] = [];
    let resolvePatch: ((value: SourcePlugin) => void) | undefined;
    const patched = new Promise<SourcePlugin>((resolve) => {
      resolvePatch = resolve;
    });
    server.use(
      http.patch("/api/v1/source-plugins/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json(await patched);
      }),
    );
    await openScreen();
    const toggle = within(await rowOf("GDELT")).getByRole("switch", { name: "Enabled, GDELT" });

    await user.click(toggle);

    await waitFor(() => {
      expect(toggle).toBeDisabled();
    });
    expect(bodies).toEqual([{ enabled: false }]);
    resolvePatch?.({ ...gdelt, enabled: false, available: false });
    await waitFor(() => {
      expect(toggle).toHaveAttribute("aria-checked", "false");
    });
    await waitFor(() => {
      expect(
        screen
          .getAllByRole("status")
          .some((element) => element.textContent?.includes("GDELT switched off")),
      ).toBe(true);
    });
  });
});

describe("SourcePluginsScreen limits (FR-061, G4)", () => {
  it("saves on blur and on Enter, sends only when changed; Escape restores", async () => {
    const user = userEvent.setup();
    arrangePlugins(SEVEN_PLUGINS);
    const bodies: Schemas["SourcePluginUpdate"][] = [];
    server.use(
      http.patch("/api/v1/source-plugins/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...gdelt, rate_limit_per_minute: 45 });
      }),
    );
    await openScreen();
    const input = within(await rowOf("GDELT")).getByLabelText("Requests per minute, GDELT");

    // No change: blur sends nothing.
    input.focus();
    await user.tab();
    expect(bodies).toEqual([]);

    // Changed, then Enter.
    await user.clear(input);
    await user.type(input, "45");
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(bodies).toEqual([{ rate_limit_per_minute: 45 }]);
    });

    // Escape restores the contract's value without sending.
    await user.clear(input);
    await user.type(input, "99");
    await user.keyboard("{Escape}");
    expect(input).toHaveValue(45);
    await user.tab();
    expect(bodies).toEqual([{ rate_limit_per_minute: 45 }]);
  });

  it("an emptied daily quota sends daily_quota: null", async () => {
    const user = userEvent.setup();
    arrangePlugins([plugin({ code: "GDELT", daily_quota: 500 })]);
    const bodies: Schemas["SourcePluginUpdate"][] = [];
    server.use(
      http.patch("/api/v1/source-plugins/{code}", async ({ request, response }) => {
        bodies.push(await request.json());
        return response(200).json({ ...gdelt, daily_quota: null });
      }),
    );
    await openScreen();
    const input = within(await rowOf("GDELT")).getByLabelText("Daily quota, GDELT");
    expect(input).toHaveValue(500);

    await user.clear(input);
    await user.tab();

    await waitFor(() => {
      expect(bodies).toEqual([{ daily_quota: null }]);
    });
  });
});

describe("SourcePluginsScreen errors (FR-007, FR-120)", () => {
  it("a VALIDATION error of a limit shows under its input and keeps the typed value; a 503 shows an error callout, never a toast", async () => {
    const user = userEvent.setup();
    arrangePlugins([gdelt]);
    server.use(
      http.patch("/api/v1/source-plugins/{code}", () =>
        errorResponse(
          errorEnvelope("VALIDATION", "The input is invalid.", {
            fields: [{ field: "rate_limit_per_minute", message: "Input should be greater than 0" }],
          }),
          422,
        ),
      ),
    );
    await openScreen();
    const input = within(await rowOf("GDELT")).getByLabelText("Requests per minute, GDELT");
    await user.clear(input);
    await user.type(input, "0");
    await user.tab();

    expect(await screen.findByText("Input should be greater than 0")).toBeInTheDocument();
    expect(input).toHaveValue(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    server.use(
      http.patch("/api/v1/source-plugins/{code}", () =>
        errorResponse(errorEnvelope("UPSTREAM_UNAVAILABLE", "The database is unavailable."), 503),
      ),
    );
    await user.clear(input);
    await user.type(input, "5");
    await user.tab();

    expect(await screen.findByRole("alert")).toHaveTextContent("The database is unavailable.");
    expect(
      screen.queryAllByRole("status").some((element) => element.textContent?.includes("saved")),
    ).toBe(false);
  });
});

describe("SourcePluginsScreen states (FR-005, FR-006, FR-118)", () => {
  it("loading shows skeleton rows; an error shows its message and Retry; a 403 shows Not allowed; a 503 DATABASE shows the Degradation wording", async () => {
    signedInAs(olgaAdmin);
    server.use(
      http.get("/api/v1/source-plugins", () =>
        errorResponse(errorEnvelope("INTERNAL", "Something went wrong on our side."), 500),
      ),
    );
    renderApp("/settings/source-plugins");
    expect(await screen.findByText("Something went wrong on our side.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    server.use(
      http.get("/api/v1/source-plugins", () =>
        errorResponse(errorEnvelope("FORBIDDEN", "Not allowed for this account."), 403),
      ),
    );
    renderApp("/settings/source-plugins");
    expect(await screen.findByRole("heading", { name: "Not allowed" })).toBeInTheDocument();

    server.use(
      http.get("/api/v1/source-plugins", () =>
        errorResponse(
          errorEnvelope("UPSTREAM_UNAVAILABLE", "Unavailable.", { dependency: "DATABASE" }),
          503,
        ),
      ),
    );
    renderApp("/settings/source-plugins");
    expect(await screen.findByText("The database is unavailable.")).toBeInTheDocument();
  });
});

describe("SourcePluginsScreen page anatomy (FR-103, FR-104)", () => {
  it("the page header has the title and one lead sentence and no primary button", async () => {
    arrangePlugins(SEVEN_PLUGINS);
    await openScreen();
    const heading = screen.getByRole("heading", { name: "Source plug-ins", level: 1 });
    expect(
      screen.getByText(
        "See what each source reads, whether it can run now, and adjust its switch and limits.",
      ),
    ).toBeInTheDocument();
    const header = heading.closest("div");
    expect(header?.querySelector("button")).toBeNull();
  });
});
