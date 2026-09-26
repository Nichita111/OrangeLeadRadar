import type { Schemas } from "./contract";

export const anaSales: Schemas["User"] = {
  id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a01",
  email: "sales@leadradar.local",
  display_name: "Ana Sales",
  role: "SALES",
  status: "ACTIVE",
  last_login_at: "2026-09-01T08:00:00Z",
};

export const olgaAdmin: Schemas["User"] = {
  id: "0b6f6f3e-5f0a-4f0e-9d0e-1a1a1a1a1a02",
  email: "admin@leadradar.local",
  display_name: "Olga Admin",
  role: "ADMIN",
  status: "ACTIVE",
  last_login_at: "2026-09-01T08:00:00Z",
};

export function authenticatedUser(user: Schemas["User"]): Schemas["AuthenticatedUser"] {
  return { id: user.id, email: user.email, display_name: user.display_name, role: user.role };
}

export function errorEnvelope(
  code: string,
  message: string,
  details?: NonNullable<Schemas["ErrorEnvelope"]["error"]["details"]>,
): Schemas["ErrorEnvelope"] {
  return { error: details === undefined ? { code, message } : { code, message, details } };
}
