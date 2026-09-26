// `FR-014`: page, sort and filters round-trip through the URL.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useSearchParams } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

import { useListParams } from "./listParams";
import { Pagination } from "./Pagination";

function ListParamsProbe() {
  const [params, setParams] = useListParams(["status"]);
  const [searchParams] = useSearchParams();
  return (
    <div>
      <p data-testid="page">{params.page}</p>
      <p data-testid="sort">{params.sort ?? ""}</p>
      <p data-testid="status">{params.filters.status ?? ""}</p>
      <p data-testid="query">{searchParams.toString()}</p>
      <button
        onClick={() => {
          setParams({ page: 2, sort: "priority", filters: { status: "ACTIVE" } });
        }}
      >
        change
      </button>
    </div>
  );
}

describe("useListParams", () => {
  it("round-trips page, sort and filters through the URL query", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/prospects"]}>
        <ListParamsProbe />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("page")).toHaveTextContent("1");

    await user.click(screen.getByRole("button", { name: "change" }));

    expect(screen.getByTestId("page")).toHaveTextContent("2");
    expect(screen.getByTestId("sort")).toHaveTextContent("priority");
    expect(screen.getByTestId("status")).toHaveTextContent("ACTIVE");
    expect(screen.getByTestId("query")).toHaveTextContent("page=2&sort=priority&status=ACTIVE");
  });

  it("reads page, page_size and total from the answer", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    const { container } = render(
      <Pagination page={2} pageSize={25} total={80} onPageChange={onPageChange} />,
    );
    expect(screen.getByText("Page 2 of 4")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(onPageChange).toHaveBeenCalledWith(3);
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
