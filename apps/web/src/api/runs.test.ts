import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { http, server } from "../testServer";
import type { Schemas } from "./contract";
import { activationRescore, useSourcePlugins, useUpdateSourcePlugin, type Run } from "./runs";

function run(overrides: Partial<Run>): Run {
  return {
    id: crypto.randomUUID(),
    kind: "RESCORE",
    trigger: "FEEDBACK",
    status: "QUEUED",
    stage: null,
    progress: {},
    errors: [],
    account: null,
    service: null,
    question: null,
    requested_by_name: null,
    created_at: "2026-09-27T00:00:00Z",
    started_at: null,
    finished_at: null,
    ai_cost_eur: 0,
    ...overrides,
  };
}

describe("activationRescore (G1 b, FR-036)", () => {
  it("picks the first SCORING_ACTIVATION run above account rescores of the same service", () => {
    const activation = run({ id: "activation", trigger: "SCORING_ACTIVATION" });
    const runs = [run({ id: "feedback", trigger: "FEEDBACK" }), activation];
    expect(activationRescore(runs)).toBe(activation);
  });

  it("is undefined when there is no SCORING_ACTIVATION run", () => {
    const runs = [run({ trigger: "FEEDBACK" }), run({ trigger: "OVERRIDE" })];
    expect(activationRescore(runs)).toBeUndefined();
  });

  it("is undefined for an empty list", () => {
    expect(activationRescore([])).toBeUndefined();
  });
});

function plugin(overrides: Partial<Schemas["SourcePlugin"]>): Schemas["SourcePlugin"] {
  return {
    code: "GDELT",
    enabled: true,
    rate_limit_per_minute: 10,
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

function sharedClientWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useUpdateSourcePlugin (API-38)", () => {
  it("replaces only the patched plug-in in the source-plugins cache with the api's answer", async () => {
    const gdelt = plugin({ code: "GDELT" });
    const rss = plugin({ code: "RSS" });
    server.use(
      http.get("/api/v1/source-plugins", ({ response }) => response(200).json([gdelt, rss])),
      http.patch("/api/v1/source-plugins/{code}", ({ response }) =>
        response(200).json({ ...gdelt, enabled: false }),
      ),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const wrapper = sharedClientWrapper(queryClient);

    const list = renderHook(() => useSourcePlugins(), { wrapper });
    await waitFor(() => {
      expect(list.result.current.data).toEqual([gdelt, rss]);
    });
    const update = renderHook(() => useUpdateSourcePlugin(), { wrapper });
    update.result.current.mutate({ code: "GDELT", body: { enabled: false } });

    await waitFor(() => {
      expect(list.result.current.data).toEqual([{ ...gdelt, enabled: false }, rss]);
    });
  });
});
