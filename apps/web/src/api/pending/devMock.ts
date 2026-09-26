/**
 * Development-only stand-in for the api contracts that are not built yet (`API-39` to `API-45`
 * and the catalogues the Prospects screens read). `main.tsx` imports it only under
 * `import.meta.env.DEV`, so it never reaches the production build (`npm run check:build`).
 */
import { fixtureFetch } from "../../features/prospect-dashboard/fixtures";

const API_PREFIX = "/api/v1";

export function installDevMock(): void {
  const realFetch = window.fetch.bind(window);
  const mock = fixtureFetch();
  window.fetch = (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return url.startsWith(API_PREFIX) ? mock(input, init) : realFetch(input, init);
  };
  console.info("pending-dev-mock: /api/v1 is answered by fixtures");
}
