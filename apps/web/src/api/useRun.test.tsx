// [ADR-13](/architecture/adrs/adr-13-run-progress-by-polling.md); `FR-012`: polls at
// `RUN_POLL_INTERVAL_MS` while `RUNNING` and stops once the run is final.
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useRun } from "./runs";
import { createTestQueryClient, queryWrapper } from "./queryTestUtils";

const RUN_BASE = {
  id: "11111111-1111-1111-1111-111111111111",
  kind: "ACCOUNT_REFRESH",
  trigger: "USER",
  stage: "FETCH",
  progress: {},
  errors: [],
  account: null,
  service: null,
  question: null,
  requested_by_name: null,
  created_at: null,
  started_at: null,
  finished_at: null,
  ai_cost_eur: 0,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useRun", () => {
  it("polls every RUN_POLL_INTERVAL_MS while RUNNING and stops once final", async () => {
    vi.useFakeTimers();
    let call = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      call += 1;
      const status = call < 3 ? "RUNNING" : "SUCCEEDED";
      return Promise.resolve(jsonResponse({ ...RUN_BASE, status }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useRun(RUN_BASE.id, 1000), {
      wrapper: queryWrapper(queryClient),
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data?.status).toBe("RUNNING");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data?.status).toBe("RUNNING");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data?.status).toBe("RUNNING");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.data?.status).toBe("SUCCEEDED");

    const callsAtFinal = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAtFinal);
  });
});
