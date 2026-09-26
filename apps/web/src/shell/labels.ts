/**
 * The words the screens show for glossary terms ([Screen labels]
 * (/architecture/services/frontend.md#screen-labels), `FR-008`). Each map is exhaustive over the
 * generated enum, so a new value is a type error here.
 */
import type { FindingStatus, Band, Standing } from "../api/prospects";
import type { components } from "../api/schema.gen";

type FindingDecidedBy = components["schemas"]["FindingDecidedBy"];

export const STANDING_LABELS: Record<Standing, string> = {
  RANKED: "Ranked",
  BELOW_FIT: "Below fit",
  DISQUALIFIED: "Excluded",
  CUSTOMER: "Customer",
};

export const BAND_LABELS: Record<Band, string> = { HOT: "Hot", WARM: "Warm", COLD: "Cold" };

export const DECIDED_BY_LABELS: Record<FindingDecidedBy, string> = {
  CLASSIFIER: "Quick check",
  LLM: "Detailed check",
};

export const FINDING_STATUS_LABELS: Record<FindingStatus, string> = {
  ACTIVE: "Counting",
  REJECTED: "Marked wrong",
  SUPERSEDED: "Outdated question",
};
