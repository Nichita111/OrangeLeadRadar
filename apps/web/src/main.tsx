import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { bootstrap } from "./bootstrap";
import { loadClientConfig } from "./shell/config";
import { Providers } from "./shell/providers";
import "./styles/app.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("root element not found");
}
const root = createRoot(container);

async function start(): Promise<void> {
  const config = await loadClientConfig();
  await bootstrap(
    config,
    async () => {
      const { worker } = await import("./mocks/browser");
      await worker.start({ onUnhandledRequest: "bypass" });
    },
    () => {
      root.render(
        <StrictMode>
          <Providers config={config}>
            <App />
          </Providers>
        </StrictMode>,
      );
    },
  );
}

void start();
