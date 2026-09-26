/**
 * Query hooks of `API-07` to `API-13` ([Services and questions]
 * (/architecture/interfaces.md#services-and-questions)). Two query key families, `["services",
 * ...]` and `["services", serviceId, "questions"]`; a service or question write invalidates the
 * whole `["services"]` prefix, since a question's status changes its service's `question_count`.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { components } from "./schema.gen";

export type Service = components["schemas"]["Service"];
export type ServiceCreate = components["schemas"]["ServiceCreate"];
export type ServiceUpdate = components["schemas"]["ServiceUpdate"];
export type ServiceStatus = components["schemas"]["ServiceStatus"];

export type SignalQuestion = components["schemas"]["SignalQuestion"];
export type SignalQuestionCreate = components["schemas"]["SignalQuestionCreate"];
export type SignalQuestionUpdate = components["schemas"]["SignalQuestionUpdate"];
export type SignalQuestionAnswerType = components["schemas"]["SignalQuestionAnswerType"];
export type SignalQuestionPolarity = components["schemas"]["SignalQuestionPolarity"];
export type SignalQuestionStatus = components["schemas"]["SignalQuestionStatus"];
export type QuestionOption = components["schemas"]["QuestionOption"];
export type DocumentSourceType = components["schemas"]["DocumentSourceType"];

export const servicesQueryKey = ["services"] as const;
export const serviceQueryKey = (id: string) => ["services", id] as const;
export const questionsQueryKey = (serviceId: string) =>
  ["services", serviceId, "questions"] as const;

/** `API-07`. */
export function useServices(): UseQueryResult<Service[]> {
  return useQuery({
    queryKey: servicesQueryKey,
    queryFn: () => apiRequest<Service[]>("/services"),
  });
}

/** `API-09`. */
export function useService(id: string): UseQueryResult<Service> {
  return useQuery({
    queryKey: serviceQueryKey(id),
    queryFn: () => apiRequest<Service>(`/services/${id}`),
  });
}

export function useCreateService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ServiceCreate) => apiRequest<Service>("/services", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: servicesQueryKey });
    },
  });
}

export function useUpdateService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ServiceUpdate }) =>
      apiRequest<Service>(`/services/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: servicesQueryKey });
    },
  });
}

/** `API-11`. */
export function useQuestions(serviceId: string): UseQueryResult<SignalQuestion[]> {
  return useQuery({
    queryKey: questionsQueryKey(serviceId),
    queryFn: () => apiRequest<SignalQuestion[]>(`/services/${serviceId}/questions`),
  });
}

export function useCreateQuestion(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SignalQuestionCreate) =>
      apiRequest<SignalQuestion>(`/services/${serviceId}/questions`, { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: servicesQueryKey });
    },
  });
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: SignalQuestionUpdate }) =>
      apiRequest<SignalQuestion>(`/questions/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: servicesQueryKey });
    },
  });
}
