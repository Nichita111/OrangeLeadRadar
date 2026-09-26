import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, unwrap, unwrapNoContent } from "./client";
import type { components } from "./schema.gen";

export const authKeys = {
  currentUser: ["auth", "me"] as const,
};

/** `API-03`: the signed-in user, or `undefined` while anonymous (a `401`). */
export interface CurrentUserQuery {
  data: components["schemas"]["User"] | undefined;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

export function useCurrentUser(): CurrentUserQuery {
  return useQuery({
    queryKey: authKeys.currentUser,
    queryFn: async () => unwrap(await apiClient.GET("/api/v1/auth/me")),
    retry: false,
  });
}

/** `API-02`, then drops the cached current user (`FR-004`). */
export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      unwrapNoContent(await apiClient.POST("/api/v1/auth/logout", {}));
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: authKeys.currentUser });
    },
  });
}
