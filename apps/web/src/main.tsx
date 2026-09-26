import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { loadConfig } from "./config";
import { createAppRouter } from "./router";
import "./styles/index.css";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("root element not found");
}
const root = createRoot(container);

async function boot(): Promise<void> {
  // The development mock of the pending contracts API-01 to API-06; the production build drops this
  // block. It is deleted with src/api/pending/ when the api declares those paths.
  if (import.meta.env.DEV) {
    const { startDevMock } = await import("./api/pending/devServer");
    await startDevMock(import.meta.env);
  }
  const config = await loadConfig();
  root.render(
    <StrictMode>
      <App config={config} router={createAppRouter()} />
    </StrictMode>,
  );
}

boot().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : "The client could not start.";
  root.render(<p role="alert">{message}</p>);
});
