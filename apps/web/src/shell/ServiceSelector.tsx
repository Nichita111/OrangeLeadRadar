import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import type { components } from "../api/schema.gen";
import { useServices } from "../api/services";
import { Select } from "../components/ui/select";
import { ErrorState } from "./states/ErrorState";
import { LoadingRows } from "./states/LoadingRows";

type Service = components["schemas"]["Service"];
interface SelectedServiceValue {
  service: Service | undefined;
  active: Service[];
  select: (value: string) => void;
}
const SelectedServiceContext = createContext<SelectedServiceValue | undefined>(undefined);

export function ServiceSelectorProvider({
  userId,
  children,
}: {
  userId: string;
  children: ReactNode;
}): ReactElement {
  const query = useServices();
  if (query.error instanceof Error)
    return (
      <ErrorState
        message={query.error.message}
        retry={() => {
          void query.refetch();
        }}
      />
    );
  if (query.isPending || query.data === undefined) return <LoadingRows />;
  return (
    <LoadedServiceSelectorProvider userId={userId} services={query.data}>
      {children}
    </LoadedServiceSelectorProvider>
  );
}

function LoadedServiceSelectorProvider({
  userId,
  services,
  children,
}: {
  userId: string;
  services: Service[];
  children: ReactNode;
}): ReactElement {
  const active = useMemo(
    () => services.filter((service) => service.status === "ACTIVE"),
    [services],
  );
  const storageKey = `leadradar:selected-service:${userId}`;
  const [selectedId, setSelectedId] = useState(() => localStorage.getItem(storageKey) ?? "");
  const selected = active.find((service) => service.id === selectedId) ?? active[0];

  useEffect(() => {
    if (selected !== undefined && selected.id !== selectedId) {
      setSelectedId(selected.id);
      localStorage.setItem(storageKey, selected.id);
    }
  }, [selected, selectedId, storageKey]);

  function select(value: string): void {
    setSelectedId(value);
    localStorage.setItem(storageKey, value);
  }

  return (
    <SelectedServiceContext.Provider value={{ service: selected, active, select }}>
      {children}
    </SelectedServiceContext.Provider>
  );
}

export function useSelectedService(): Service | undefined {
  return useContext(SelectedServiceContext)?.service;
}

export function ServiceSelector(): ReactElement {
  const context = useContext(SelectedServiceContext);
  if (context === undefined) throw new Error("ServiceSelector used outside its provider");
  return (
    <Select
      value={context.service?.id}
      onValueChange={context.select}
      options={context.active.map((service) => ({ value: service.id, label: service.name }))}
      ariaLabel="Service"
    />
  );
}
