/**
 * Query hooks of `API-01` to `API-03` ([Authentication and users]
 * (/architecture/interfaces.md#authentication-and-users)). One query key family, `["auth", ...]`,
 * per [TypeScript guidelines](/guidelines/typescript.md#react-and-server-state).
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, apiRequest } from "./client";
import type { components } from "./schema.gen";

export type AuthenticatedUser = components["schemas"]["AuthenticatedUser"];
export type LoginRequest = components["schemas"]["LoginRequest"];

export const authMeQueryKey = ["auth", "me"] as const;

/** The signed-in user, or `null` while anonymous (`401`); never throws for that expected case, so
 * a route guard can render from `data` alone. */
export function useMe(): UseQueryResult<AuthenticatedUser | null> {
  return useQuery({
    queryKey: authMeQueryKey,
    queryFn: async () => {
      try {
        return await apiRequest<AuthenticatedUser>("/auth/me", { redirectOnUnauthorized: false });
      } catch (error) {
        if (error instanceof ApiError) {
          return null;
        }
        throw error;
      }
    },
    retry: false,
    staleTime: Infinity,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) =>
      apiRequest<AuthenticatedUser>("/auth/login", {
        method: "POST",
        body,
        redirectOnUnauthorized: false,
      }),
    onSuccess: (user) => {
      queryClient.setQueryData(authMeQueryKey, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<undefined>("/auth/logout", { method: "POST" }),
    onSuccess: () => {
      queryClient.setQueryData(authMeQueryKey, null);
    },
  });
}
