import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { client, requireData } from "./client";
import type { Schemas } from "./contract";

/** One query key family for [Services and questions](/architecture/interfaces.md#services-and-questions). */
export const servicesAndQuestionsKeys = {
  services: ["services-and-questions", "services"] as const,
  service: (id: string) => ["services-and-questions", "services", id] as const,
  questions: (serviceId: string) => ["services-and-questions", "questions", serviceId] as const,
};

/** `API-07`. */
export function useServices() {
  return useQuery({
    queryKey: servicesAndQuestionsKeys.services,
    queryFn: async () => requireData((await client.GET("/api/v1/services")).data),
  });
}

/** `API-09`. */
export function useService(id: string | undefined) {
  return useQuery({
    queryKey: servicesAndQuestionsKeys.service(id ?? ""),
    enabled: id !== undefined,
    queryFn: async () =>
      requireData(
        (await client.GET("/api/v1/services/{id}", { params: { path: { id: id ?? "" } } })).data,
      ),
  });
}

async function invalidateServices(queryClient: ReturnType<typeof useQueryClient>): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: ["services-and-questions"] });
}

/** `API-08`. */
export function useCreateService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["ServiceCreate"]) =>
      requireData((await client.POST("/api/v1/services", { body })).data),
    onSuccess: async () => {
      await invalidateServices(queryClient);
    },
  });
}

/** `API-10`. */
export function useUpdateService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Schemas["ServiceUpdate"] }) =>
      requireData(
        (await client.PATCH("/api/v1/services/{id}", { params: { path: { id } }, body })).data,
      ),
    onSuccess: async () => {
      await invalidateServices(queryClient);
    },
  });
}

/** `API-11`. */
export function useQuestions(serviceId: string | undefined) {
  return useQuery({
    queryKey: servicesAndQuestionsKeys.questions(serviceId ?? ""),
    enabled: serviceId !== undefined,
    queryFn: async () =>
      requireData(
        (
          await client.GET("/api/v1/services/{id}/questions", {
            params: { path: { id: serviceId ?? "" } },
          })
        ).data,
      ),
  });
}

/** `API-12`. */
export function useCreateQuestion(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["SignalQuestionCreate"]) =>
      requireData(
        (
          await client.POST("/api/v1/services/{id}/questions", {
            params: { path: { id: serviceId } },
            body,
          })
        ).data,
      ),
    onSuccess: async () => {
      await invalidateServices(queryClient);
    },
  });
}

/** `API-13`. */
export function useUpdateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Schemas["SignalQuestionUpdate"] }) =>
      requireData(
        (await client.PATCH("/api/v1/questions/{id}", { params: { path: { id } }, body })).data,
      ),
    onSuccess: async () => {
      await invalidateServices(queryClient);
    },
  });
}
