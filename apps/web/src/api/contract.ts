// The one import point for contract types. While the pending fragment exists it is composed with the
// api's snapshot; when task 2's snapshot declares the paths, this file reduces to the api's types.
import type { components as PendingComponents, paths as PendingPaths } from "./pending/schema.gen";
import type { components as ApiComponents, paths as ApiPaths } from "./schema.gen";

export type paths = ApiPaths & PendingPaths;
export type Schemas = ApiComponents["schemas"] & PendingComponents["schemas"];
