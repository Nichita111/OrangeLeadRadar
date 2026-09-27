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
  // The development mock of the contracts not yet built (TypeScript Mock layer); the production
  // build drops this block, which `check:build` verifies. A family's handlers are deleted when
  // the api builds it.
  if (import.meta.env.DEV) {
    const { startDevMock } = await import("./mocks/devServer");
    await startDevMock();
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
