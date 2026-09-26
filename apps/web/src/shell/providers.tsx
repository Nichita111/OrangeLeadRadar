import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { BrowserRouter } from "react-router";

import { ApiError } from "../api/errors";
import { ConfigProvider, type ClientConfig } from "./config";
import { Toaster } from "./feedback/Toaster";

function returnToSignIn(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    const returnPath = `${window.location.pathname}${window.location.search}`;
    window.location.assign(`/login?return=${encodeURIComponent(returnPath)}`);
  }
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({ onError: returnToSignIn }),
    mutationCache: new MutationCache({ onError: returnToSignIn }),
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function Providers({ config, children }: { config: ClientConfig; children: ReactElement }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <ConfigProvider value={config}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
        <Toaster />
      </QueryClientProvider>
    </ConfigProvider>
  );
}
