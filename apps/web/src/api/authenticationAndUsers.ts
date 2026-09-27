import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, client, requireData } from "./client";
import type { Schemas } from "./contract";
import { READS_OWN_UNAUTHENTICATED } from "./queryClient";

/** One query key family for the interface family Authentication and users. */
export const authenticationAndUsersKeys = {
  me: ["authentication-and-users", "me"] as const,
  users: ["authentication-and-users", "users"] as const,
  invites: ["authentication-and-users", "invites"] as const,
  invitePreview: (token: string) => ["authentication-and-users", "invite-preview", token] as const,
};

/** Refetch on focus or reconnect only while there is a user whose session could have ended. */
const whileSignedIn = (query: { state: { data: unknown } }) => query.state.data !== undefined;

/**
 * `API-03`: the signed-in user; a `401` is read by the route guard and by Sign in (DC-3). A visitor
 * who is not signed in is not asked again when the window regains focus: that refetch would send
 * the query back to pending and unmount the anonymous screen, losing what was typed.
 */
export function useMe() {
  return useQuery({
    queryKey: authenticationAndUsersKeys.me,
    meta: READS_OWN_UNAUTHENTICATED,
    refetchOnWindowFocus: whileSignedIn,
    refetchOnReconnect: whileSignedIn,
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
        (await client.PATCH("/api/v1/users/{id}", { params: { path: { id: id } }, body })).data,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: authenticationAndUsersKeys.users });
    },
  });
}

/** `API-83`: the pending invites, newest first. */
export function useInvites() {
  return useQuery({
    queryKey: authenticationAndUsersKeys.invites,
    queryFn: async () => requireData((await client.GET("/api/v1/invites")).data),
  });
}

/** `API-79`: the answer carries the link, once. */
export function useCreateInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["InviteCreate"]) =>
      requireData((await client.POST("/api/v1/invites", { body })).data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: authenticationAndUsersKeys.invites });
    },
  });
}

/** `API-80`. */
export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await client.POST("/api/v1/invites/{id}/revoke", { params: { path: { id } } });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: authenticationAndUsersKeys.invites });
    },
  });
}

/** `API-81`: previews the invite whose token the link's fragment carries, anonymously. */
export function useInvitePreview(token: string) {
  return useQuery({
    queryKey: authenticationAndUsersKeys.invitePreview(token),
    meta: READS_OWN_UNAUTHENTICATED,
    retry: false,
    queryFn: async () =>
      requireData((await client.POST("/api/v1/auth/invite", { body: { token } })).data),
  });
}

/** `API-82`: accepts the invite and puts the new user in the `me` query. */
export function useAcceptInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: READS_OWN_UNAUTHENTICATED,
    mutationFn: async (body: Schemas["InviteAccept"]) =>
      requireData((await client.POST("/api/v1/auth/invite/accept", { body })).data),
    onSuccess: (user) => {
      queryClient.setQueryData(authenticationAndUsersKeys.me, user);
    },
  });
}
