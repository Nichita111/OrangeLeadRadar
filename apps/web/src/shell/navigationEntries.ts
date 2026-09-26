export type NavIconName =
  | "Target"
  | "Bell"
  | "Buildings"
  | "Sparkle"
  | "ArrowsClockwise"
  | "Tag"
  | "SlidersHorizontal"
  | "Factory"
  | "SealCheck"
  | "PuzzlePiece"
  | "Users"
  | "Receipt";

export interface NavEntry {
  label: string;
  route: string;
  icon: NavIconName;
}

// The Entry, Route and Icon table of frontend Navigation; a test compares the two.
export const WORK_ENTRIES: NavEntry[] = [
  { label: "Prospects", route: "/prospects", icon: "Target" },
  { label: "Alerts", route: "/alerts", icon: "Bell" },
  { label: "Accounts", route: "/accounts", icon: "Buildings" },
  { label: "Suggested accounts", route: "/suggested-accounts", icon: "Sparkle" },
  { label: "Runs", route: "/runs", icon: "ArrowsClockwise" },
  { label: "Labelling", route: "/labelling", icon: "Tag" },
];

export const ADMIN_ENTRIES: NavEntry[] = [
  { label: "Services", route: "/services", icon: "SlidersHorizontal" },
  { label: "Industries and markets", route: "/settings/industries-markets", icon: "Factory" },
  { label: "Quality", route: "/quality", icon: "SealCheck" },
  { label: "Source plug-ins", route: "/settings/source-plugins", icon: "PuzzlePiece" },
  { label: "Users", route: "/users", icon: "Users" },
  { label: "Audit log", route: "/audit", icon: "Receipt" },
];
