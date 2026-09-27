// The one import point for contract types: the api's generated client. Every REST contract of
// interfaces.md is declared from the start (`api Design` "Declared contracts"), so this file
// holds no hand-written fragment.
import type { components, paths as ApiPaths } from "./schema.gen";

export type paths = ApiPaths;
export type Schemas = components["schemas"];
