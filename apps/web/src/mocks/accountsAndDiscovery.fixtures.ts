// Typed fixtures of the Accounts and contacts (contacts only) and Discovery contracts not yet
// built, for the development mock (TypeScript Mock layer). Deleted family by family as the api
// builds each one. The contacts belong to the prospects fixtures' accounts; the candidates are
// invented companies on `.example` domains, suggested for Intelligent Automation (`svc-1`).
import type { Schemas } from "../api/contract";

type Contact = Schemas["Contact"];
type ContactSuggestion = Schemas["ContactSuggestion"];
type DiscoveryCandidate = Schemas["DiscoveryCandidate"];

/** Contact suggestions (`API-91`) by account; the mock leaves out a name already a contact. */
export const contactSuggestions: Record<string, ContactSuggestion[]> = {
  "acc-dhl": [
    {
      full_name: "Katrin Vogel",
      job_title: "Chief Information Officer",
      source_url: "https://dhl.com/en/about-us/board.html",
      quote: "Katrin Vogel, Chief Information Officer, leads the group's IT.",
      document_title: "Board of Management",
      published_at: "2026-08-05T00:00:00Z",
    },
    {
      full_name: "Dr. Henrik Albers",
      job_title: "Head of Intelligent Automation",
      source_url: "https://dhl.com/en/press/releases/2026/automation-programme.html",
      quote:
        "“We automate 1,000 processes this year,” said Dr. Henrik Albers, Head of Intelligent Automation.",
      document_title: "DHL scales AI agents across its processes",
      published_at: "2026-09-02T00:00:00Z",
    },
  ],
  "acc-lh": [
    {
      full_name: "Mira Hoffmann",
      job_title: "Head of Global Business Services",
      source_url: "https://lufthansa.com/newsroom/gbs-appointment",
      quote: "Mira Hoffmann becomes Head of Global Business Services.",
      document_title: "New head of Global Business Services",
      published_at: "2026-07-14T00:00:00Z",
    },
    {
      full_name: "Jan-Erik Brandt",
      job_title: "Leiter Prozessexzellenz",
      source_url: "https://lufthansa.com/newsroom/fit-for-growth",
      quote: "Jan-Erik Brandt, Leiter Prozessexzellenz, verantwortet das Programm Fit for Growth.",
      document_title: "Fit for Growth",
      published_at: null,
    },
  ],
};

export const contacts: Contact[] = [
  {
    id: "con-1",
    account_id: "acc-dhl",
    full_name: "Katrin Vogel",
    job_title: "Chief Information Officer",
    source_url: "https://dhl.com/en/about-us/board.html",
    persona: "CIO",
    persona_origin: "CLASSIFIER",
    retain_until: "2027-09-01",
  },
  {
    id: "con-2",
    account_id: "acc-dhl",
    full_name: "Jonas Brandt",
    job_title: "Leiter Prozessexzellenz",
    source_url: "https://dhl.com/en/press/releases/2026/new-process-lead.html",
    persona: "HEAD_OF_PROCESS_EXCELLENCE",
    persona_origin: "MANUAL",
    retain_until: "2027-08-12",
  },
  {
    id: "con-3",
    account_id: "acc-lh",
    full_name: "Mira Hoffmann",
    job_title: "Head of Global Business Services",
    source_url: "https://lufthansa.com/newsroom/gbs-appointment",
    persona: "HEAD_OF_SHARED_SERVICES",
    persona_origin: "CLASSIFIER",
    retain_until: "2027-07-30",
  },
];

function candidate(
  id: string,
  name: string,
  fitEstimate: number,
  extra: Partial<DiscoveryCandidate>,
): DiscoveryCandidate {
  return {
    id,
    service_id: "svc-1",
    name,
    domain: null,
    country_code: null,
    industry: null,
    employee_count: null,
    origin: "CRUNCHBASE_SEARCH",
    status: "PENDING",
    fit_estimate: fitEstimate,
    evidence: null,
    reject_reason: null,
    account_id: null,
    ...extra,
  };
}

export const discoveryCandidates: DiscoveryCandidate[] = [
  candidate("cand-1", "Nordhafen Logistik", 86, {
    domain: "nordhafen-logistik.example",
    country_code: "DE",
    industry: "LOGISTICS_TRANSPORT",
    employee_count: 12000,
  }),
  candidate("cand-2", "Alpenflug", 74, {
    domain: "alpenflug.example",
    country_code: "AT",
    industry: "AEROSPACE_AVIATION",
    employee_count: 6800,
    origin: "NEWS_MENTION",
    evidence: {
      document_id: "doc-disc-1",
      title: "Alpenflug launches a finance automation programme",
      url: "https://news.example/alpenflug-finance-automation",
      published_at: "2026-09-18T00:00:00Z",
      quote: "Alpenflug plans to automate its accounts payable process with RPA by 2027.",
    },
  }),
  // No domain: accepting it needs one entered by the user.
  candidate("cand-3", "Rheinwerk Versicherung", 61, {
    country_code: "DE",
    industry: "INSURANCE",
    origin: "NEWS_MENTION",
    evidence: {
      document_id: "doc-disc-2",
      title: "Rheinwerk Versicherung consolidates claims handling in a shared service centre",
      url: "https://news.example/rheinwerk-shared-services",
      published_at: "2026-09-10T00:00:00Z",
      quote:
        "The insurer will move claims handling for four countries into one shared service centre.",
    },
  }),
  candidate("cand-4", "Kvist Bank", 48, {
    domain: "kvistbank.example",
    country_code: "DK",
    industry: "BANKING",
    employee_count: 5400,
  }),
  candidate("cand-5", "Lagune Retail", 22, {
    domain: "lagune-retail.example",
    country_code: "IT",
    industry: "RETAIL_CONSUMER",
    employee_count: 900,
    status: "REJECTED",
    reject_reason: "Too small for this service.",
  }),
];

/** Proposed by the mock's discovery run when it finishes. */
export const discoveredLater: DiscoveryCandidate = candidate("cand-6", "Brenner Bahnlogistik", 79, {
  domain: "brenner-bahnlogistik.example",
  country_code: "CH",
  industry: "LOGISTICS_TRANSPORT",
  employee_count: 7300,
});
