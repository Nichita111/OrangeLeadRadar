import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { createTestQueryClient, queryWrapper } from "./queryTestUtils";
import { useSignOut } from "./auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

it("FR-004 accepts API-02's successful 204 response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  const queryClient = createTestQueryClient();
  const { result } = renderHook(() => useSignOut(), { wrapper: queryWrapper(queryClient) });

  await act(async () => {
    await result.current.mutateAsync();
  });

  expect(fetch).toHaveBeenCalledOnce();
});
