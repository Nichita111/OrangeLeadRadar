const DEFAULT_TARGET = "/prospects";

/** FR-093: a return path is followed only when it is a path of this client. */
export function safeReturnPath(value: string | null): string {
  if (value === null || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return DEFAULT_TARGET;
  }
  return value;
}
