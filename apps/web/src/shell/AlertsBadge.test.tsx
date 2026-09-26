import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { useUnreadAlertCount } from "../api/alerts";
import { createTestQueryClient, queryWrapper } from "../api/queryTestUtils";
import { AlertsBadge } from "./AlertsBadge";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("AlertsBadge", () => {
  it("FR-002 shows positive unread counts", async () => {
    const { container } = render(<AlertsBadge count={3} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
  it("FR-002 hides zero", async () => {
    const { container } = render(<AlertsBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });

  it("FR-013 refetches unread count on its interval and window focus", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], page: 1, page_size: 25, total: 3 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = createTestQueryClient();
    renderHook(() => useUnreadAlertCount("service-1", 1000), {
      wrapper: queryWrapper(queryClient),
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      window.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
