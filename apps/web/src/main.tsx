import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { loadRuntimeConfig } from "./api/config";
import { createQueryClient } from "./api/queryClient";
import { ToastProvider } from "./components/Toast";
import { ConfigProvider } from "./shell/config-context";
import "./styles/tokens.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("root element not found");
}

const queryClient = createQueryClient();

// The client reads `/config.json`, written by the `web` container at start-up, before its first
// render ([Design](/architecture/services/frontend.md#design)).
void loadRuntimeConfig().then((config) => {
  createRoot(container).render(
    <StrictMode>
      <ConfigProvider value={config}>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ToastProvider>
        </QueryClientProvider>
      </ConfigProvider>
    </StrictMode>,
  );
});
