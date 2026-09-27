import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useConfig } from "../configContext";
import { client, requireData } from "./client";
import type { Schemas } from "./contract";
import { referenceDataKeys } from "./referenceData";

export type AccountRow = Schemas["AccountRow"];

/** One query key family for the interface family Accounts. */
export const accountsKeys = ["accounts"] as const;

export interface AccountFilters {
  q: string;
  status: Schemas["AccountStatus"] | undefined;
  origin: Schemas["AccountOrigin"] | undefined;
  page: number;
}

/**
 * `API-20` (`FR-038`). Polls every `RUN_POLL_INTERVAL_MS` while a listed account's refresh is
 * running, so its Refreshing mark clears when the run ends (`FR-137`).
 */
export function useAccounts(filters: AccountFilters) {
  const { RUN_POLL_INTERVAL_MS } = useConfig();
  return useQuery({
    queryKey: [...accountsKeys, "list", filters],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/accounts", {
            params: {
              query: {
                page: filters.page,
                ...(filters.q.trim() === "" ? {} : { q: filters.q.trim() }),
                ...(filters.status === undefined ? {} : { status: filters.status }),
                ...(filters.origin === undefined ? {} : { origin: filters.origin }),
              },
            },
          })
        ).data,
      ),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((account) => account.active_run_id !== null)
        ? RUN_POLL_INTERVAL_MS
        : false,
  });
}

/** `API-21` (`FR-039`). */
export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["AccountCreate"]) =>
      requireData((await client.POST("/api/v1/accounts", { body })).data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKeys }),
  });
}

/** `API-24` (`FR-044` to `FR-047`). */
export function useUpdateAccount(accountId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["AccountUpdate"]) =>
      requireData(
        (
          await client.PATCH("/api/v1/accounts/{id}", {
            params: { path: { id: accountId } },
            body,
          })
        ).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: accountsKeys });
      await queryClient.invalidateQueries({ queryKey: referenceDataKeys });
    },
  });
}

/** `API-22`: a dry run checks the file and writes nothing (`FR-041`, `FR-043`). */
export function useImportAccounts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, dryRun }: { file: File; dryRun: boolean }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", String(dryRun));
      return requireData(
        (
          await client.POST("/api/v1/accounts/import", {
            body: { file: "", dry_run: dryRun },
            bodySerializer: () => form,
          })
        ).data,
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKeys }),
  });
}
