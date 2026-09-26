import type { Schemas } from "../../../api/contract";

export type Role = Schemas["User"]["role"];

// The `role` values of `app_user`; the assertion below fails to compile if the contract adds one.
export const ROLES = ["SALES", "ADMIN"] as const satisfies readonly Role[];
export const allRolesListed: Role extends (typeof ROLES)[number] ? true : never = true;
