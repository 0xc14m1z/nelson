import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

// Stable mock data (declared outside mock factory via vi.hoisted to avoid infinite re-renders)
const { mockModels, mockMutateFn } = vi.hoisted(() => ({
  mockModels: [
    { id: "m1", slug: "gpt-4o", display_name: "GPT-4o", provider_slug: "openai" },
    { id: "m2", slug: "claude-3", display_name: "Claude 3", provider_slug: "anthropic" },
    { id: "m3", slug: "gpt-4o-mini", display_name: "GPT-4o Mini", provider_slug: "openai" },
  ],
  mockMutateFn: vi.fn(),
}));

// Mock @mantine/core with lightweight components to avoid OOM from emotion CSS-in-JS
vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  const Checkbox = Object.assign(
    (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox", value: props.value }), props.label),
    { Group: wrap() }
  );
  return {
    Box: wrap(), Button: wrap(), Checkbox, Group: wrap(),
    MantineProvider: wrap(), NumberInput: wrap(), Stack: wrap(),
    Switch: (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox" }), props.label),
    Text: wrap(), Textarea: (props: Record<string, unknown>) =>
      R.createElement("div", null, props.label as string),
    Title: (props: Record<string, unknown>) =>
      R.createElement(`h${props.order || 1}`, null, props.children),
  };
});
vi.mock("@mantine/notifications", () => ({ notifications: { show: vi.fn() } }));

vi.mock("@tanstack/react-query", async () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const actual = require("@tanstack/react-query");
  return {
    ...actual,
    useQuery: () => ({ data: mockModels, isLoading: false }),
    useMutation: (opts: Record<string, unknown>) => ({
      mutate: mockMutateFn,
      mutateAsync: mockMutateFn,
      isPending: false,
      ...opts,
    }),
  };
});

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(), setAccessToken: vi.fn(), getAccessToken: vi.fn(),
}));
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "test@example.com", display_name: null, billing_mode: "own_keys" },
    isAuthenticated: true, isLoading: false,
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import NewSessionPage from "../page";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NewSessionPage />
    </QueryClientProvider>
  );
}

describe("New Session Page", () => {
  it("renders enquiry form with model selector", () => {
    renderPage();
    expect(screen.getByText("New Enquiry")).toBeInTheDocument();
    expect(screen.getByText("Your question")).toBeInTheDocument();
    expect(screen.getByText("Select models (minimum 2)")).toBeInTheDocument();
    expect(screen.getByText("Start Consensus")).toBeInTheDocument();
  });

  it("shows models grouped by provider", () => {
    renderPage();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    expect(screen.getByText("Claude 3")).toBeInTheDocument();
    expect(screen.getByText("GPT-4o Mini")).toBeInTheDocument();
  });

  it("renders start button", () => {
    renderPage();
    expect(screen.getByText("Start Consensus")).toBeInTheDocument();
  });
});
