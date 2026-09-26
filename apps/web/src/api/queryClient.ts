import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

/**
 * Meta for a query or mutation whose `401` is read by its caller and must not send the user to
 * Sign in: `API-01` (wrong credentials) and the `me` query (the route guard and Sign in read it).
 */
export const READS_OWN_UNAUTHENTICATED = { readsOwnUnauthenticated: true } as const;

function readsOwnUnauthenticated(meta: Record<string, unknown> | undefined): boolean {
  return meta?.["readsOwnUnauthenticated"] === true;
}

/**
 * FR-006: a `401` from any call other than `API-01` hands the current route to `onUnauthenticated`,
 * which sends the user to Sign in with it as return path, and clears the cache. There are no
 * retries: a failed call is shown, never repeated silently.
 */
export function createQueryClient(onUnauthenticated: () => void): QueryClient {
  const handle = (error: unknown, meta: Record<string, unknown> | undefined) => {
    if (error instanceof ApiError && error.status === 401 && !readsOwnUnauthenticated(meta)) {
      // Navigate first: the screen that made the call leaves before the cleared cache can refetch.
      onUnauthenticated();
      queryClient.clear();
    }
  };
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        handle(error, query.meta);
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        handle(error, mutation.meta);
      },
    }),
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return queryClient;
}
