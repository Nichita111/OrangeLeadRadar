import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { useServices } from "../api/services";
import { ServiceSelectorProvider, useSelectedService } from "./ServiceSelector";

vi.mock("../api/services", () => ({ useServices: vi.fn() }));
const mockedServices = vi.mocked(useServices);
const services = [
  {
    id: "active-1",
    code: "ONE",
    name: "One",
    description: "",
    value_proposition: "",
    status: "ACTIVE" as const,
    active_version: 1,
    draft_version: null,
    question_count: 0,
  },
  {
    id: "inactive",
    code: "OLD",
    name: "Old",
    description: "",
    value_proposition: "",
    status: "INACTIVE" as const,
    active_version: null,
    draft_version: null,
    question_count: 0,
  },
  {
    id: "active-2",
    code: "TWO",
    name: "Two",
    description: "",
    value_proposition: "",
    status: "ACTIVE" as const,
    active_version: 1,
    draft_version: null,
    question_count: 0,
  },
];
function Selected() {
  return <span>{useSelectedService()?.name}</span>;
}

describe("ServiceSelector", () => {
  const values = new Map<string, string>();
  beforeEach(() => {
    values.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      clear: () => {
        values.clear();
      },
      removeItem: (key: string) => {
        values.delete(key);
      },
      key: () => null,
      length: 0,
    });
    mockedServices.mockReturnValue({ data: services } as ReturnType<typeof useServices>);
  });
  it("FR-003 restores an active choice per user", () => {
    values.set("leadradar:selected-service:user-1", "active-2");
    render(
      <ServiceSelectorProvider userId="user-1">
        <Selected />
      </ServiceSelectorProvider>,
    );
    expect(screen.getByText("Two")).toBeInTheDocument();
  });
  it("FR-003 falls back to the first active service", async () => {
    values.set("leadradar:selected-service:user-1", "inactive");
    render(
      <ServiceSelectorProvider userId="user-1">
        <Selected />
      </ServiceSelectorProvider>,
    );
    expect(screen.getByText("One")).toBeInTheDocument();
    await waitFor(() => {
      expect(values.get("leadradar:selected-service:user-1")).toBe("active-1");
    });
  });

  it("FR-005 preserves the services loading and error states", async () => {
    mockedServices.mockReturnValueOnce({ isPending: true } as ReturnType<typeof useServices>);
    const { container, rerender } = render(
      <ServiceSelectorProvider userId="user-1">
        <Selected />
      </ServiceSelectorProvider>,
    );
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();

    const refetch = vi.fn();
    mockedServices.mockReturnValue({
      isPending: false,
      error: new Error("Services failed"),
      refetch,
    } as ReturnType<typeof useServices>);
    rerender(
      <ServiceSelectorProvider userId="user-1">
        <Selected />
      </ServiceSelectorProvider>,
    );
    expect(screen.getByText("Services failed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalledOnce();
    expect((await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations).toEqual([]);
  });
});
