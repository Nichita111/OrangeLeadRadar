/**
 * The service every screen shows ([Navigation](/architecture/services/frontend.md#navigation),
 * `FR-003`): the user's choice among the `ACTIVE` services of `API-07`, remembered per user in
 * `localStorage`; with no valid choice, the first active service.
 */
import { createContext, useContext, useState, type ReactNode } from "react";

import { useServices, type Service } from "../api/services";
import { useCurrentUser } from "./current-user-context";

interface ServiceSelection {
  isLoading: boolean;
  /** The failure of `API-07`, so screens do not read it as "no active service". */
  error: unknown;
  refetch: () => void;
  active: Service[];
  service: Service | null;
  select: (serviceId: string) => void;
}

const SelectedServiceContext = createContext<ServiceSelection | null>(null);

export function SelectedServiceProvider({ children }: { children: ReactNode }) {
  const user = useCurrentUser();
  const storageKey = `leadradar.service.${user.id}`;
  const { data, isLoading, error, refetch } = useServices();
  const [chosenId, setChosenId] = useState(() => localStorage.getItem(storageKey));

  const active = (data ?? []).filter((candidate) => candidate.status === "ACTIVE");
  const service = active.find((candidate) => candidate.id === chosenId) ?? active[0] ?? null;

  const select = (serviceId: string) => {
    localStorage.setItem(storageKey, serviceId);
    setChosenId(serviceId);
  };

  return (
    <SelectedServiceContext.Provider
      value={{
        isLoading,
        error,
        refetch: () => {
          void refetch();
        },
        active,
        service,
        select,
      }}
    >
      {children}
    </SelectedServiceContext.Provider>
  );
}

/** The whole selection, for the selector and for screens that tell loading from "none active". */
export function useServiceSelection(): ServiceSelection {
  const selection = useContext(SelectedServiceContext);
  if (selection === null) {
    throw new Error("useServiceSelection must be used within a SelectedServiceProvider");
  }
  return selection;
}
