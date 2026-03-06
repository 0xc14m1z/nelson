import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export interface Provider {
  id: string;
  slug: string;
  display_name: string;
  base_url: string;
  is_active: boolean;
}

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

export interface ApiKey {
  id: string;
  provider_id: string;
  provider_slug: string;
  provider_display_name: string;
  masked_key: string;
  is_valid: boolean;
  validated_at: string | null;
  created_at: string;
}

export interface UserSettings {
  max_rounds: number | null;
  default_model_ids: string[];
  summarizer_model_id: string | null;
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

export function useProviders() {
  return useQuery<Provider[]>({
    queryKey: ["providers"],
    queryFn: async () => {
      const resp = await apiFetch("/api/providers");
      if (!resp.ok) throw new Error("Failed to fetch providers");
      return resp.json();
    },
  });
}

export function useModels(providerId?: string) {
  return useQuery<Model[]>({
    queryKey: ["models", providerId],
    queryFn: async () => {
      const url = providerId
        ? `/api/models?provider_id=${providerId}`
        : "/api/models";
      const resp = await apiFetch(url);
      if (!resp.ok) throw new Error("Failed to fetch models");
      return resp.json();
    },
  });
}

export function useApiKeys() {
  return useQuery<ApiKey[]>({
    queryKey: ["apiKeys"],
    queryFn: async () => {
      const resp = await apiFetch("/api/keys");
      if (!resp.ok) throw new Error("Failed to fetch API keys");
      return resp.json();
    },
  });
}

export function useUserSettings() {
  return useQuery<UserSettings>({
    queryKey: ["userSettings"],
    queryFn: async () => {
      const resp = await apiFetch("/api/users/me/settings");
      if (!resp.ok) throw new Error("Failed to fetch settings");
      return resp.json();
    },
  });
}

export function useStoreKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      providerId,
      apiKey,
    }: {
      providerId: string;
      apiKey: string;
    }) => {
      const resp = await apiFetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider_id: providerId, api_key: apiKey }),
      });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data.detail || "Failed to store key");
      }
      return resp.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useDeleteKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const resp = await apiFetch(`/api/keys/${providerId}`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error("Failed to delete key");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useValidateKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const resp = await apiFetch(`/api/keys/${providerId}/validate`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error("Failed to validate key");
      return resp.json();
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["apiKeys"] }),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (settings: {
      max_rounds?: number | null;
      default_model_ids?: string[];
      summarizer_model_id?: string | null;
    }) => {
      const resp = await apiFetch("/api/users/me/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!resp.ok) throw new Error("Failed to update settings");
      return resp.json();
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["userSettings"] }),
  });
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

export function useOpenRouterModels(enabled: boolean) {
  return useQuery<OpenRouterModel[]>({
    queryKey: ["openrouterModels"],
    queryFn: async () => {
      const resp = await apiFetch("/api/openrouter/models");
      if (!resp.ok) throw new Error("Failed to fetch OpenRouter models");
      return resp.json();
    },
    enabled,
    staleTime: 5 * 60 * 1000,
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
