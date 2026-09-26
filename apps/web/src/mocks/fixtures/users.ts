import type { components } from "../../api/schema.gen";

// PLACEHOLDER(invented): replace ids and display names with the seeded user records.
export const users: Record<components["schemas"]["AppUserRole"], components["schemas"]["User"]> = {
  SALES: {
    id: "user-sales",
    email: "sales@leadradar.local",
    display_name: "Sales demo",
    role: "SALES",
    status: "ACTIVE",
    last_login_at: null,
  },
  ADMIN: {
    id: "user-admin",
    email: "admin@leadradar.local",
    display_name: "Admin demo",
    role: "ADMIN",
    status: "ACTIVE",
    last_login_at: null,
  },
};
