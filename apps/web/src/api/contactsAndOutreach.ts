import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type Contact = Schemas["Contact"];
export type ContactCreate = Schemas["ContactCreate"];
export type ContactUpdate = Schemas["ContactUpdate"];
export type ContactPersona = Schemas["ContactPersona"];
export type ContactSuggestion = Schemas["ContactSuggestion"];
export type OutreachDraft = Schemas["OutreachDraft"];
export type OutreachDraftChannel = Schemas["OutreachDraftChannel"];
export type OutreachDraftUpdate = Schemas["OutreachDraftUpdate"];
export type OutreachPreferences = Schemas["OutreachPreferences"];
export type ToneCheck = Schemas["ToneCheck"];

export const CONTACT_PERSONAS: readonly ContactPersona[] = [
  "CIO",
  "CTO",
  "COO",
  "CFO",
  "CISO",
  "HEAD_OF_DIGITAL_TRANSFORMATION",
  "HEAD_OF_AUTOMATION",
  "HEAD_OF_PROCESS_EXCELLENCE",
  "HEAD_OF_SHARED_SERVICES",
  "OTHER",
];

/** One query key family for contacts (`API-25` to `API-28`) and outreach drafts (`API-56` to `API-58`). */
export const contactsAndOutreachKeys = ["contacts-and-outreach"] as const;

/** `API-25`. */
export function useContacts(accountId: string) {
  return useQuery({
    queryKey: [...contactsAndOutreachKeys, "contacts", accountId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/accounts/{id}/contacts", {
            params: { path: { id: accountId } },
          })
        ).data,
      ),
  });
}

/** `API-26`, `API-27` and `API-28`; each refreshes the account's contacts. */
export function useContactMutations(accountId: string) {
  const queryClient = useQueryClient();
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: [...contactsAndOutreachKeys] });
  const create = useMutation({
    mutationFn: async (body: ContactCreate) =>
      requireData(
        (
          await client.POST("/api/v1/accounts/{id}/contacts", {
            params: { path: { id: accountId } },
            body,
          })
        ).data,
      ),
    onSuccess,
  });
  const update = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: ContactUpdate }) =>
      requireData(
        (await client.PATCH("/api/v1/contacts/{id}", { params: { path: { id } }, body })).data,
      ),
    onSuccess,
  });
  const erase = useMutation({
    mutationFn: async (id: string) => {
      await client.DELETE("/api/v1/contacts/{id}", { params: { path: { id } } });
    },
    onSuccess,
  });
  return { create, update, erase };
}

/** `API-94`: computed on request from the account's stored documents; nothing is stored. */
export function useContactSuggestions(accountId: string) {
  return useMutation({
    mutationFn: async () =>
      requireData(
        (
          await client.POST("/api/v1/accounts/{id}/contact-suggestions", {
            params: { path: { id: accountId } },
          })
        ).data,
      ),
  });
}

/** `API-57`: newest first. */
export function useOutreachDrafts(accountId: string, serviceId: string) {
  return useQuery({
    queryKey: [...contactsAndOutreachKeys, "drafts", accountId, serviceId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/accounts/{id}/outreach-drafts", {
            params: { path: { id: accountId }, query: { service_id: serviceId } },
          })
        ).data,
      ),
  });
}

/** `API-79`: active Orange Systems facts applicable to a service. */
export function useProviderFacts(serviceId: string) {
  return useQuery({
    queryKey: [...contactsAndOutreachKeys, "provider-facts", serviceId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/provider-facts", {
            params: { query: { status: "ACTIVE", service_id: serviceId } },
          })
        ).data,
      ),
  });
}

/** `API-56` (generate) and `API-58` (save or export); each refreshes the drafts. */
export function useOutreachMutations(accountId: string, serviceId: string) {
  const queryClient = useQueryClient();
  const onSuccess = () =>
    queryClient.invalidateQueries({
      queryKey: [...contactsAndOutreachKeys, "drafts", accountId, serviceId],
    });
  const generate = useMutation({
    mutationFn: async (body: Schemas["OutreachRequest"]) =>
      requireData(
        (
          await client.POST("/api/v1/accounts/{id}/scores/{service_id}/outreach-drafts", {
            params: { path: { id: accountId, service_id: serviceId } },
            body,
          })
        ).data,
      ),
    onSuccess,
  });
  const update = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: OutreachDraftUpdate }) =>
      requireData(
        (await client.PATCH("/api/v1/outreach-drafts/{id}", { params: { path: { id } }, body }))
          .data,
      ),
    onSuccess,
  });
  const toneCheck = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Schemas["ToneCheckRequest"] }) =>
      requireData(
        (
          await client.POST("/api/v1/outreach-drafts/{id}/tone-check", {
            params: { path: { id } },
            body,
          })
        ).data,
      ),
  });
  const markContacted = useMutation({
    mutationFn: async (id: string) =>
      requireData(
        (
          await client.POST("/api/v1/outreach-drafts/{id}/mark-contacted", {
            params: { path: { id } },
          })
        ).data,
      ),
  });
  return { generate, update, toneCheck, markContacted };
}
