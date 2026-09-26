import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import type { DataRouter } from "react-router";
import { RouterProvider } from "react-router/dom";

import { createQueryClient } from "./api/queryClient";
import { ToastProvider } from "./components/Toast";
import type { Config } from "./config";
import { ConfigProvider } from "./configContext";

/** The client: its runtime configuration, server state, toasts and the router. */
export function App({ config, router }: { config: Config; router: DataRouter }) {
  const [queryClient] = useState(() =>
    createQueryClient(() => {
      const { pathname, search } = router.state.location;
      // Already on Sign in: a call of the screen just left answered late; nothing more to do.
      if (pathname === "/login") {
        return;
      }
      void router.navigate(`/login?return=${encodeURIComponent(`${pathname}${search}`)}`, {
        replace: true,
      });
    }),
  );
  return (
    <ConfigProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
