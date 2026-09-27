import type { Schemas } from "../../../api/contract";

export type SourcePlugin = Schemas["SourcePlugin"];

export type Availability =
  | { kind: "AVAILABLE" }
  | { kind: "SWITCHED_OFF" }
  | { kind: "KEY_MISSING" }
  | { kind: "QUOTA_REACHED" };

/**
 * `FR-143`: the reason `SourcePlugin.available` is false, named from the same fields in the
 * order [Plug-in availability](/architecture/rules.md#plug-in-availability) reads them — the
 * switch, then the key, then the quota. The rule's one implementation decides `available`; this
 * function only names which input it refused.
 */
export function availability(plugin: SourcePlugin): Availability {
  if (plugin.available) {
    return { kind: "AVAILABLE" };
  }
  if (!plugin.enabled) {
    return { kind: "SWITCHED_OFF" };
  }
  if (plugin.needs_key && !plugin.key_configured) {
    return { kind: "KEY_MISSING" };
  }
  return { kind: "QUOTA_REACHED" };
}

/**
 * `FR-060`: true whenever the plug-in needs a key it does not have, whatever the switch — a
 * switched-off plug-in whose key is missing still carries this note.
 */
export function keyNote(plugin: SourcePlugin): boolean {
  return plugin.needs_key && !plugin.key_configured;
}
