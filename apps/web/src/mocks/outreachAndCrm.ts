// The development mock of Outreach and CRM (`API-56` to `API-59`), so the Outreach composer drafts
// from the account's own signals (TypeScript Mock layer). Temporary: the draft is written from a
// template instead of the LLM, over the same inputs as Outreach grounding — the service's value
// proposition, up to `OUTREACH_MAX_FINDINGS` counted positive findings by points, the contact and
// the requesting user — and cites every finding it quotes; the HubSpot push always succeeds.
import { createOpenApiHttp } from "openapi-msw";

import { errorEnvelope, errorResponse } from "../api/authenticationAndUsers.fixtures";
import type { Schemas, paths } from "../api/contract";
import { mockSessionUser } from "./authentication";
import { findings, scoreViews, services } from "./prospectsAndEvidence.fixtures";
import type { MockStore } from "./store";

type Channel = Schemas["OutreachDraftChannel"];
type Contact = Schemas["Contact"];
type FindingView = Schemas["FindingView"];

const PRIMARY_PROVIDER_FACT: Schemas["ProviderFact"] = {
  id: "00000000-0000-4000-8000-000000009001",
  text: "Orange Systems has automated more than 750 processes with RPA.",
  source_url: "https://www.orange.md/",
  services: [],
  status: "ACTIVE",
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

const PROVIDER_FACTS: Schemas["ProviderFact"][] = [
  PRIMARY_PROVIDER_FACT,
  {
    id: "00000000-0000-4000-8000-000000009002",
    text: "Orange Systems is a UiPath Platinum Partner.",
    source_url: "https://www.orange.md/",
    services: [],
    status: "ACTIVE",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  },
];

/** `OUTREACH_MAX_FINDINGS`, `OUTREACH_EMAIL_MAX_CHARS` and `OUTREACH_INMAIL_MAX_CHARS`. */
const OUTREACH_MAX_FINDINGS = 5;
const MAX_CHARS: Record<Channel, number> = { EMAIL: 1200, LINKEDIN_INMAIL: 1900 };

/** How many findings the template quotes; the rest stay available to the person editing. */
const QUOTED_FINDINGS = 2;

/** The account's counted positive findings for the service, most points first. */
export function groundingFindings(accountId: string, serviceId: string): FindingView[] {
  return findings
    .filter(
      (finding) =>
        finding.account_id === accountId &&
        finding.service_id === serviceId &&
        finding.status === "ACTIVE" &&
        finding.question.polarity === "POSITIVE" &&
        finding.points !== null &&
        finding.points > 0,
    )
    .sort((left, right) => (right.points ?? 0) - (left.points ?? 0))
    .slice(0, OUTREACH_MAX_FINDINGS);
}

function sentenceCase(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

function draftText(
  channel: Channel,
  accountName: string,
  service: Schemas["Service"],
  cited: FindingView[],
  contact: Contact | undefined,
  sender: string,
): { subject: string | null; body: string } {
  const [lead, second] = cited;
  if (lead === undefined) {
    throw new Error("a draft needs at least one finding");
  }
  // The quote's own closing stop is dropped, as the sentence around it supplies one.
  const quote = (finding: FindingView) =>
    `“${(finding.quote_en ?? finding.quote).replace(/[.!?]+$/, "")}”`;
  const greeting = contact === undefined ? "Hello," : `Dear ${contact.full_name},`;
  const opening = `I read ${accountName}'s recent announcement: ${quote(lead)}`;
  const follow =
    second === undefined
      ? ""
      : ` Together with your ${sentenceCase(second.question.text)} (${quote(second)}), it suggests the next step is scale rather than pilots.`;
  const role =
    contact === undefined
      ? ""
      : ` As ${contact.job_title}, you are probably weighing where to start.`;
  const pitch = service.value_proposition === "" ? "" : `\n\n${service.value_proposition}`;
  const close =
    channel === "EMAIL"
      ? `Would a 20-minute call next week be useful to compare notes on where automation pays off first?\n\nBest regards,\n${sender}\nOrange Systems`
      : `Open to a short exchange on where automation pays off first?\n\n${sender}, Orange Systems`;
  const body = `${greeting}\n\n${opening}.${follow}${role}${pitch}\n\n${close}`;
  return {
    subject: channel === "EMAIL" ? `${accountName}: ${lead.question.text} — a next step` : null,
    body: body.slice(0, MAX_CHARS[channel]),
  };
}

export function createOutreachAndCrmHandlers(store: MockStore) {
  const http = createOpenApiHttp<paths>({ baseUrl: window.location.origin });
  const notFound = () => errorResponse(errorEnvelope("NOT_FOUND", "Not found."), 404);

  return [
    http.post(
      "/api/v1/accounts/{id}/scores/{service_id}/outreach-drafts",
      async ({ params, request, response }) => {
        const account = store.accounts.find((row) => row.id === params.id);
        const service = services.find((row) => row.id === params.service_id);
        if (account === undefined || service === undefined) {
          return notFound();
        }
        const body = await request.json();
        const contact = store.contacts.find(
          (row) => row.id === body.contact_id && row.account_id === account.id,
        );
        if (body.contact_id !== undefined && contact === undefined) {
          return errorResponse(
            errorEnvelope("VALIDATION", "The input is invalid.", {
              fields: [{ field: "contact_id", message: "Not a contact of this account." }],
            }),
            422,
          );
        }
        const given = groundingFindings(account.id, service.id);
        if (given.length === 0) {
          return errorResponse(
            errorEnvelope(
              "VALIDATION",
              "The account has no in-force positive signal for this service.",
            ),
            422,
          );
        }
        const preferences = body.preferences;
        const citedCount =
          preferences?.personalization === "STANDARD"
            ? 1
            : preferences?.personalization === "TAILORED"
              ? 2
              : OUTREACH_MAX_FINDINGS;
        if (preferences?.personalization === "TAILORED" && given.length < 2) {
          return errorResponse(
            errorEnvelope("VALIDATION", "Tailored needs at least two eligible signals."),
            422,
          );
        }
        if (preferences?.personalization === "BESPOKE" && contact === undefined) {
          return errorResponse(
            errorEnvelope("VALIDATION", "Bespoke needs a selected contact."),
            422,
          );
        }
        const cited = given.slice(0, preferences === undefined ? QUOTED_FINDINGS : citedCount);
        const sender = mockSessionUser().display_name;
        const text = draftText(body.channel, account.name, service, cited, contact, sender);
        const draft: Schemas["OutreachDraft"] = {
          id: store.newId(),
          account_id: account.id,
          service_id: service.id,
          channel: body.channel,
          status: "DRAFT",
          edited: false,
          created_at: new Date().toISOString(),
          created_by_name: sender,
          preferences: preferences ?? null,
          contact:
            contact === undefined
              ? null
              : { id: contact.id, full_name: contact.full_name, job_title: contact.job_title },
          findings: cited.map((finding) => ({
            id: finding.id,
            question_text: finding.question.text,
            quote: finding.quote,
          })),
          provider_facts: [{ id: PRIMARY_PROVIDER_FACT.id, text: PRIMARY_PROVIDER_FACT.text }],
          ...text,
        };
        store.drafts.unshift(draft);
        return response(200).json(draft);
      },
    ),
    http.get("/api/v1/accounts/{id}/outreach-drafts", ({ params, query, response }) => {
      const serviceId = query.get("service_id");
      return response(200).json(
        store.drafts.filter(
          (draft) => draft.account_id === params.id && draft.service_id === serviceId,
        ),
      );
    }),
    http.patch("/api/v1/outreach-drafts/{id}", async ({ params, request, response }) => {
      const draft = store.drafts.find((row) => row.id === params.id);
      if (draft === undefined) {
        return notFound();
      }
      const body = await request.json();
      if (body.status === "DRAFT" && draft.status === "EXPORTED") {
        return errorResponse(
          errorEnvelope("VALIDATION", "The input is invalid.", {
            fields: [{ field: "status", message: "An exported draft stays exported." }],
          }),
          422,
        );
      }
      if (
        (body.subject !== undefined && body.subject !== draft.subject) ||
        (body.body !== undefined && body.body !== draft.body)
      ) {
        draft.edited = true;
      }
      Object.assign(draft, body);
      return response(200).json(draft);
    }),
    http.get("/api/v1/provider-facts", ({ response }) => response(200).json(PROVIDER_FACTS)),
    http.post("/api/v1/outreach-drafts/{id}/tone-check", async ({ params, request, response }) => {
      const draft = store.drafts.find((row) => row.id === params.id);
      if (draft === undefined) {
        return notFound();
      }
      const body = await request.json();
      const tooGeneric = body.body.toLowerCase().includes("hope this finds you well");
      return response(200).json({
        verdict: tooGeneric ? "REVIEW" : "GOOD",
        summary: tooGeneric
          ? "Replace the generic opening with the selected evidence."
          : "The message matches the selected tone.",
        notes: tooGeneric
          ? [
              {
                phrase: "hope this finds you well",
                suggested_rewrite: "I noticed your recent automation announcement",
              },
            ]
          : [],
      });
    }),
    http.post("/api/v1/outreach-drafts/{id}/mark-contacted", ({ params, response }) => {
      const draft = store.drafts.find((row) => row.id === params.id);
      if (draft === undefined) {
        return notFound();
      }
      return response(200).json({
        id: store.newId(),
        service_id: draft.service_id,
        status: "CONTACTED",
        origin: "MANUAL",
        occurred_at: new Date().toISOString(),
        note: null,
        created_at: new Date().toISOString(),
        set_by_name: mockSessionUser().display_name,
      });
    }),
    http.post("/api/v1/accounts/{id}/scores/{service_id}/crm-push", ({ params, response }) => {
      const scored = scoreViews.some(
        (score) => score.account_id === params.id && score.service_id === params.service_id,
      );
      if (!scored) {
        return notFound();
      }
      return response(200).json({
        id: store.newId(),
        target: "HUBSPOT",
        status: "SUCCEEDED",
        external_id: `mock-${params.id}`,
        error: null,
        created_at: new Date().toISOString(),
      });
    }),
  ];
}
