/**
 * Query hooks of `API-04` to `API-06` ([Authentication and users]
 * (/architecture/interfaces.md#authentication-and-users)). One query key family, `["users", ...]`.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type User = components["schemas"]["User"];
export type UserCreate = components["schemas"]["UserCreate"];
export type UserUpdate = components["schemas"]["UserUpdate"];
export type AppUserRole = components["schemas"]["AppUserRole"];
export type AppUserStatus = components["schemas"]["AppUserStatus"];

export const usersQueryKey = ["users"] as const;

/** `API-04`: ordered by `display_name`, as the api returns it. */
export function useUsers(): UseQueryResult<User[]> {
  return useQuery({
    queryKey: usersQueryKey,
    queryFn: () => apiRequest<User[]>("/users"),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => apiRequest<User>("/users", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: usersQueryKey });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UserUpdate }) =>
      apiRequest<User>(`/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: usersQueryKey });
    },
  });
}
