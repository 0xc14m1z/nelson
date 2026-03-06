import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Model {
  id: string;
  provider_id: string;
  provider_slug: string;
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string;
  output_price_per_mtok: string;
  is_active: boolean;
  context_window: number;
  tokens_per_second: number | null;
}

export interface CustomModel {
  id: string;
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string;
  output_price_per_mtok: string;
  context_window: number;
  tokens_per_second: number | null;
}

export interface OpenRouterModel {
  slug: string;
  display_name: string;
  model_type: string | null;
  input_price_per_mtok: string | null;
  output_price_per_mtok: string | null;
  context_window: number | null;
  tokens_per_second: number | null;
}

export function useCustomModels() {
  return useQuery<CustomModel[]>({
    queryKey: ["customModels"],
    queryFn: async () => {
      const resp = await apiFetch("/api/users/me/custom-models");
      if (!resp.ok) throw new Error("Failed to fetch custom models");
      return resp.json();
    },
  });
}

export function useOpenRouterModels(search: string) {
  return useQuery<OpenRouterModel[]>({
    queryKey: ["openrouterModels", search],
    queryFn: async () => {
      const url = search
        ? `/api/openrouter/models?search=${encodeURIComponent(search)}`
        : "/api/openrouter/models";
      const resp = await apiFetch(url);
      if (!resp.ok) throw new Error("Failed to fetch OpenRouter models");
      return resp.json();
    },
    enabled: search.length >= 2,
  });
}

export function useAddCustomModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (model: {
      model_slug: string;
      display_name: string;
      model_type?: string | null;
      input_price_per_mtok?: number | null;
      output_price_per_mtok?: number | null;
      context_window?: number | null;
      tokens_per_second?: number | null;
    }) => {
      const resp = await apiFetch("/api/users/me/custom-models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(model),
      });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "Failed to add model");
      }
      return resp.json();
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["customModels"] }),
  });
}

export function useDeleteCustomModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (modelId: string) => {
      const resp = await apiFetch(`/api/users/me/custom-models/${modelId}`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error("Failed to delete custom model");
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["customModels"] }),
  });
}
