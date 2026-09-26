/**
 * Query hooks of [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
 * (`API-20` to `API-24`; contacts, `API-25` to `API-28`, are out of this task's scope). One query
 * key family, `["accounts", ...]`.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Account = components["schemas"]["Account"];
export type AccountRow = components["schemas"]["AccountRow"];
export type AccountCreate = components["schemas"]["AccountCreate"];
export type AccountUpdate = components["schemas"]["AccountUpdate"];
export type AccountStatus = components["schemas"]["AccountStatus"];
export type AccountOrigin = components["schemas"]["AccountOrigin"];
export type AccountOperationalComplexity = components["schemas"]["AccountOperationalComplexity"];
export type AccountSourceKind = components["schemas"]["AccountSourceKind"];
export type AccountSourceOrigin = components["schemas"]["AccountSourceOrigin"];
export type AccountSourceStatus = components["schemas"]["AccountSourceStatus"];
export type AccountSourceItem = components["schemas"]["AccountSourceItem"];
export type ImportResult = components["schemas"]["ImportResult"];
export type ImportRowItem = components["schemas"]["ImportRowItem"];
export type AccountPage = components["schemas"]["Page_AccountRow_"];

/** [`ImportResult`](/architecture/interfaces.md#importresult) `rows[].outcome`. */
export type ImportRowOutcome = "CREATED" | "UPDATED" | "POSSIBLE_DUPLICATE" | "INVALID";

export interface AccountsFilter {
  q?: string | undefined;
  status?: AccountStatus | undefined;
  country_code?: string | undefined;
  industry?: string | undefined;
  origin?: AccountOrigin | undefined;
  page?: number | undefined;
}

function accountsQueryString(filter: AccountsFilter): string {
  const params = new URLSearchParams();
  if (filter.q !== undefined && filter.q.length > 0) {
    params.set("q", filter.q);
  }
  if (filter.status !== undefined) {
    params.set("status", filter.status);
  }
  if (filter.country_code !== undefined) {
    params.set("country_code", filter.country_code);
  }
  if (filter.industry !== undefined) {
    params.set("industry", filter.industry);
  }
  if (filter.origin !== undefined) {
    params.set("origin", filter.origin);
  }
  if (filter.page !== undefined) {
    params.set("page", String(filter.page));
  }
  const qs = params.toString();
  return qs.length > 0 ? `?${qs}` : "";
}

export function accountsQueryKey(filter: AccountsFilter): readonly unknown[] {
  return ["accounts", filter] as const;
}

/** `API-20`. */
export function useAccounts(filter: AccountsFilter): UseQueryResult<AccountPage> {
  return useQuery({
    queryKey: accountsQueryKey(filter),
    queryFn: () => apiRequest<AccountPage>(`/accounts${accountsQueryString(filter)}`),
  });
}

/** `API-23`. */
export function useAccount(id: string | undefined): UseQueryResult<Account> {
  return useQuery({
    queryKey: ["accounts", "detail", id] as const,
    queryFn: () => apiRequest<Account>(`/accounts/${id ?? ""}`),
    enabled: id !== undefined,
  });
}

/** `API-21`. */
export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AccountCreate) => apiRequest<Account>("/accounts", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    },
  });
}

/** `API-24`. Any attribute change enqueues a `RESCORE` from the api; the client shows `FR-047`. */
export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AccountUpdate }) =>
      apiRequest<Account>(`/accounts/${id}`, { method: "PATCH", body }),
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["accounts", "detail", variables.id] });
    },
  });
}

/** `API-22`: a `dry_run` request never invalidates the list, since nothing is written. */
export function useImportAccounts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, dryRun }: { file: File; dryRun: boolean }) => {
      const body = new FormData();
      body.append("file", file);
      body.append("dry_run", String(dryRun));
      return apiRequest<ImportResult>("/accounts/import", { method: "POST", body });
    },
    onSuccess: (result) => {
      if (!result.dry_run) {
        void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      }
    },
  });
}
