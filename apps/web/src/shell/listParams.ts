import { useSearchParams } from "react-router";

/** `FR-014`: list state lives in the URL; `page_size` stays server-owned. */
export interface ListParams {
  page: number;
  sort: string | undefined;
  filters: Record<string, string>;
}

export function useListParams(
  filterKeys: readonly string[],
): [
  ListParams,
  (next: { page?: number; sort?: string; filters?: Record<string, string> }) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Number(searchParams.get("page") ?? "1");
  const sort = searchParams.get("sort") ?? undefined;
  const filters = Object.fromEntries(
    filterKeys
      .map((key) => [key, searchParams.get(key) ?? ""] as const)
      .filter(([, value]) => value !== ""),
  );
  function update(next: { page?: number; sort?: string; filters?: Record<string, string> }): void {
    const params = new URLSearchParams(searchParams);
    if (next.page !== undefined) params.set("page", String(next.page));
    if (next.sort !== undefined) params.set("sort", next.sort);
    if (next.filters !== undefined) {
      for (const [key, value] of Object.entries(next.filters)) {
        if (value === "") params.delete(key);
        else params.set(key, value);
      }
    }
    setSearchParams(params);
  }
  return [{ page, sort, filters }, update];
}
