import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

// Stable mock data (declared outside mock factory via vi.hoisted to avoid infinite re-renders)
const { mockEmptyData, mockSessionsData } = vi.hoisted(() => ({
  mockEmptyData: { sessions: [] },
  mockSessionsData: {
    sessions: [
      {
        id: "s1",
        enquiry: "What is the meaning of life?",
        status: "consensus_reached",
        model_ids: ["m1", "m2"],
        current_round: 3,
        total_cost: 0.0042,
        created_at: "2026-03-01T00:00:00Z",
      },
      {
        id: "s2",
        enquiry: "Explain quantum computing",
        status: "responding",
        model_ids: ["m1", "m2", "m3"],
        current_round: 1,
        total_cost: 0.0015,
        created_at: "2026-03-02T00:00:00Z",
      },
    ],
  },
}));

// Track which mock data useQuery should return
let currentQueryData: unknown = mockEmptyData;

// Mock @mantine/core with lightweight components to avoid OOM from emotion CSS-in-JS
vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  return {
    Badge: (props: Record<string, unknown>) =>
      R.createElement("span", null, props.children),
    Box: wrap(), Button: wrap(), Group: wrap(),
    MantineProvider: wrap(), Paper: wrap(), Stack: wrap(),
    Text: wrap(),
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
    useQuery: () => ({ data: currentQueryData, isLoading: false }),
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

import SessionsPage from "../page";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SessionsPage />
    </QueryClientProvider>
  );
}

describe("Sessions Page", () => {
  it("renders empty state when no sessions", () => {
    currentQueryData = mockEmptyData;
    renderPage();
    expect(screen.getByText("No sessions yet. Start your first enquiry!")).toBeInTheDocument();
  });

  it("renders session cards with status badges", () => {
    currentQueryData = mockSessionsData;
    renderPage();
    expect(screen.getByText("What is the meaning of life?")).toBeInTheDocument();
    expect(screen.getByText("consensus reached")).toBeInTheDocument();
    expect(screen.getByText("Explain quantum computing")).toBeInTheDocument();
    expect(screen.getByText("responding")).toBeInTheDocument();
  });

  it("renders new enquiry button", () => {
    currentQueryData = mockEmptyData;
    renderPage();
    expect(screen.getByText("New Enquiry")).toBeInTheDocument();
  });
});
