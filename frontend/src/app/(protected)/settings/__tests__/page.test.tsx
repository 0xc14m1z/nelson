import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

// Stable mock data
const mockProviders = [
  { id: "1", slug: "openai", display_name: "OpenAI", base_url: "https://api.openai.com/v1", is_active: true },
  { id: "2", slug: "anthropic", display_name: "Anthropic", base_url: "https://api.anthropic.com", is_active: true },
];
const mockApiKeys = [
  {
    id: "k1", provider_id: "1", provider_slug: "openai",
    provider_display_name: "OpenAI", masked_key: "****2345",
    is_valid: true, validated_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "k2", provider_id: "2", provider_slug: "anthropic",
    provider_display_name: "Anthropic", masked_key: "****6789",
    is_valid: true, validated_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
  },
];
const mockModels = [
  {
    id: "m1", provider_id: "1", provider_slug: "openai", slug: "gpt-5",
    display_name: "GPT-5", model_type: "chat", tokens_per_second: null,
    input_price_per_mtok: "1.25", output_price_per_mtok: "10.00",
    context_window: 400000, is_active: true,
  },
  {
    id: "m2", provider_id: "2", provider_slug: "anthropic", slug: "claude-opus-4-6",
    display_name: "Claude Opus 4.6", model_type: "hybrid", tokens_per_second: null,
    input_price_per_mtok: "5.00", output_price_per_mtok: "25.00",
    context_window: 1000000, is_active: true,
  },
];
const mockSettings = { max_rounds: null, default_model_ids: [] as string[] };

// Mock @mantine/core with lightweight components to avoid OOM from emotion CSS-in-JS
vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  const Tabs = Object.assign(wrap(), { Tab: wrap(), List: wrap(), Panel: wrap() });
  const Checkbox = Object.assign(
    (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox", value: props.value }), props.label),
    { Group: wrap() }
  );
  return {
    Alert: (props: Record<string, unknown>) =>
      R.createElement("div", { role: "alert" }, props.title && R.createElement("strong", null, props.title), props.children),
    Badge: wrap(), Button: wrap(), Checkbox, Container: wrap(), Divider: wrap(),
    Group: wrap(), Loader: wrap(), MantineProvider: wrap(),
    Modal: (props: Record<string, unknown>) =>
      props.opened ? R.createElement("dialog", null, props.children) : null,
    NumberInput: wrap(), Paper: wrap(), ScrollArea: { Autosize: wrap() }, Stack: wrap(),
    Switch: (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox" }), props.label),
    Tabs, Text: wrap(), TextInput: wrap(),
    Title: (props: Record<string, unknown>) =>
      R.createElement(`h${props.order || 1}`, null, props.children),
  };
});
vi.mock("@mantine/notifications", () => ({ notifications: { show: vi.fn() } }));

// Use stable references for mock data to prevent infinite re-renders
vi.mock("../../../../lib/hooks", () => ({
  useProviders: () => ({ data: mockProviders, isLoading: false }),
  useApiKeys: () => ({ data: mockApiKeys, isLoading: false }),
  useModels: () => ({ data: mockModels, isLoading: false }),
  useUserSettings: () => ({ data: mockSettings, isLoading: false }),
  useStoreKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useValidateKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSettings: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCustomModels: () => ({ data: [], isLoading: false }),
  useAddCustomModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteCustomModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenRouterModels: () => ({ data: [], isLoading: false }),
}));
vi.mock("../../../../lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "test@example.com", display_name: null, billing_mode: "own_keys" },
    isAuthenticated: true, isLoading: false,
  }),
}));
vi.mock("../../../../lib/api", () => ({
  apiFetch: vi.fn(), setAccessToken: vi.fn(), getAccessToken: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import SettingsPage from "../page";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SettingsPage />
    </QueryClientProvider>
  );
}

describe("Settings Page", () => {
  it("renders all three tabs", () => {
    renderPage();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("Default Models")).toBeInTheDocument();
    expect(screen.getByText("Preferences")).toBeInTheDocument();
  });

  it("shows stored key as masked", () => {
    renderPage();
    expect(screen.getByText("****2345")).toBeInTheDocument();
  });

  it("shows provider names", () => {
    renderPage();
    expect(screen.getAllByText("OpenAI").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Anthropic").length).toBeGreaterThanOrEqual(1);
  });

  it("shows model metadata inline with prices rounded to 2 decimals", () => {
    renderPage();
    // Price formatting: $1.25/$10.00
    expect(screen.getByText(/\$1\.25\/\$10\.00 per M tokens/)).toBeInTheDocument();
  });

  it("shows context window as K for sub-million", () => {
    renderPage();
    expect(screen.getByText("400K context")).toBeInTheDocument();
  });

  it("shows context window as M for 1 million+", () => {
    renderPage();
    expect(screen.getByText("1M context")).toBeInTheDocument();
  });

  it("shows model type badge", () => {
    renderPage();
    expect(screen.getByText("chat")).toBeInTheDocument();
    expect(screen.getByText("hybrid")).toBeInTheDocument();
  });

  it("orders providers: Anthropic before OpenAI in default models", () => {
    renderPage();
    const allText = document.body.textContent || "";
    const anthropicIdx = allText.indexOf("Claude Opus 4.6");
    const openaiIdx = allText.indexOf("GPT-5");
    expect(anthropicIdx).toBeLessThan(openaiIdx);
  });
});
