import { useMutation, useQuery } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

export type SignalQuestion = Schemas["SignalQuestion"];
export type QuestionPreviewRequest = Schemas["QuestionPreviewRequest"];
export type QuestionPreview = Schemas["QuestionPreview"];
export type ScoringPreview = Schemas["ScoringPreview"];

/** One query key family for the interface families Services and questions, and Scoring. */
export const serviceConfigurationKeys = ["service-configuration"] as const;

/** `API-11`. */
export function useServiceQuestions(serviceId: string) {
  return useQuery({
    queryKey: [...serviceConfigurationKeys, "questions", serviceId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/services/{id}/questions", {
            params: { path: { id: serviceId } },
          })
        ).data,
      ),
  });
}

/** `API-15`. */
export function useScoringConfigs(serviceId: string) {
  return useQuery({
    queryKey: [...serviceConfigurationKeys, "scoring-configs", serviceId],
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/services/{id}/scoring-configs", {
            params: { path: { id: serviceId } },
          })
        ).data,
      ),
  });
}

/** `API-20`: the accounts Try it can search. */
export function useAccountChoices() {
  return useQuery({
    queryKey: [...serviceConfigurationKeys, "account-choices"],
    queryFn: async () =>
      requireData(
        (await client.GET("/api/v1/accounts", { params: { query: { status: "ACTIVE" } } })).data,
      ),
  });
}

/** `API-14`: nothing is stored but the AI call audit rows. */
export function useQuestionPreview() {
  return useMutation({
    mutationFn: async (body: QuestionPreviewRequest) =>
      requireData((await client.POST("/api/v1/questions/preview", { body })).data),
  });
}

/** `API-19`: computed without writing. */
export function useScoringPreview() {
  return useMutation({
    mutationFn: async (configId: string) =>
      requireData(
        (
          await client.POST("/api/v1/scoring-configs/{id}/preview", {
            params: { path: { id: configId } },
          })
        ).data,
      ),
  });
}
