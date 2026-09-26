import type { components } from "../api/schema.gen";

let role: components["schemas"]["AppUserRole"] | null = null;
export const mockSession = {
  get role() {
    return role;
  },
  signIn(next: components["schemas"]["AppUserRole"]) {
    role = next;
  },
  signOut() {
    role = null;
  },
};
