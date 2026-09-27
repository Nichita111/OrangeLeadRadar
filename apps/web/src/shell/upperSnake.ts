/**
 * Formats a code or key field's raw input towards `^[A-Z][A-Z0-9_]*$`
 * ([`leadradar.api.configuration._UPPER_SNAKE`](../../../../apps/api/src/leadradar/api/configuration.py)):
 * upper-cases, turns spaces into `_`, and drops every other character the pattern forbids. Shared
 * by every code and key field: service code, question key, option key, criterion key,
 * disqualifier key, industry code and market code (`FR-019`, `FR-023`, `FR-155`). This is a
 * typing aid only; the api's `422` remains the authority on whether the result is valid.
 */
export function toUpperSnakeInput(raw: string): string {
  return raw
    .toUpperCase()
    .replaceAll(" ", "_")
    .replaceAll(/[^A-Z0-9_]/g, "");
}
