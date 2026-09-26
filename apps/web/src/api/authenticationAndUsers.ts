import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, client, requireData } from "./client";
import type { Schemas } from "./contract";
import { READS_OWN_UNAUTHENTICATED } from "./queryClient";

/** One query key family for the interface family Authentication and users. */
export const authenticationAndUsersKeys = {
  me: ["authentication-and-users", "me"] as const,
  users: ["authentication-and-users", "users"] as const,
};

/** `API-03`: the signed-in user; a `401` is read by the route guard and by Sign in (DC-3). */
export function useMe() {
  return useQuery({
    queryKey: authenticationAndUsersKeys.me,
    meta: READS_OWN_UNAUTHENTICATED,
    queryFn: async () => requireData((await client.GET("/api/v1/auth/me")).data),
  });
}

/** `API-01`: signs in and puts the user in the `me` query. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: READS_OWN_UNAUTHENTICATED,
    mutationFn: async (body: Schemas["LoginRequest"]) =>
      requireData((await client.POST("/api/v1/auth/login", { body })).data),
    onSuccess: (user) => {
      queryClient.setQueryData(authenticationAndUsersKeys.me, user);
    },
  });
}

/** `API-02`: signs out and clears the cache. A `401` means there is no session left, the goal. */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: READS_OWN_UNAUTHENTICATED,
    mutationFn: async () => {
      try {
        // The api's snapshot lists the session cookie as a required parameter; the browser sends it
        // itself (httpOnly) and openapi-fetch never serializes cookie parameters.
        await client.POST("/api/v1/auth/logout", { params: { cookie: { leadradar_session: "" } } });
      } catch (error: unknown) {
        if (!(error instanceof ApiError && error.status === 401)) {
          throw error;
        }
      }
    },
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

/** `API-04`: the users in the api's order. */
export function useUsers() {
  return useQuery({
    queryKey: authenticationAndUsersKeys.users,
    queryFn: async () => requireData((await client.GET("/api/v1/users")).data),
  });
}

/** `API-05`. */
export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["UserCreate"]) =>
      requireData((await client.POST("/api/v1/users", { body })).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: authenticationAndUsersKeys.users });
    },
  });
}

/** `API-06`. */
export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Schemas["UserUpdate"] }) =>
      requireData(
        (await client.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: id } }, body }))
          .data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: authenticationAndUsersKeys.users });
    },
  });
}
