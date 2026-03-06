import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

// Stable mock data (declared outside mock factory via vi.hoisted to avoid infinite re-renders)
const { mockModels, mockMutateFn, mockSettings } = vi.hoisted(() => ({
  mockModels: [
    { id: "m1", slug: "gpt-4o", display_name: "GPT-4o", provider_slug: "openai" },
    { id: "m2", slug: "claude-3", display_name: "Claude 3", provider_slug: "anthropic" },
    { id: "m3", slug: "gpt-4o-mini", display_name: "GPT-4o Mini", provider_slug: "openai" },
  ],
  mockMutateFn: vi.fn(),
  mockSettings: {
    default_model_ids: ["m1", "m2"],
    max_rounds: null,
    summarizer_model_id: null,
  },
}));

// Mock @mantine/core with lightweight components to avoid OOM from emotion CSS-in-JS
vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  const Pill = (props: Record<string, unknown>) =>
    R.createElement("span", null,
      props.children,
      props.withRemoveButton && R.createElement("button", {
        "aria-label": "Remove",
        onClick: props.onRemove as () => void,
        disabled: (props.removeButtonProps as Record<string, unknown>)?.disabled,
      }, "×"),
    );
  const Popover = Object.assign(wrap(), {
    Target: wrap(),
    Dropdown: wrap(),
  });
  const ScrollArea = Object.assign(wrap(), { Autosize: wrap() });
  return {
    ActionIcon: (props: Record<string, unknown>) =>
      R.createElement("button", {
        "aria-label": props["aria-label"],
        disabled: props.disabled,
        onClick: props.onClick as () => void,
      }, props.children),
    Box: wrap(),
    Group: wrap(),
    NumberInput: wrap(),
    MantineProvider: wrap(),
    Pill,
    Popover,
    ScrollArea,
    Stack: wrap(),
    Switch: (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox" }), props.label),
    Text: wrap(),
    Textarea: (props: Record<string, unknown>) =>
      R.createElement(R.Fragment, null,
        R.createElement("textarea", {
          placeholder: props.placeholder as string,
          "aria-label": "enquiry",
        }),
        props.rightSection,
      ),
    UnstyledButton: (props: Record<string, unknown>) =>
      R.createElement("button", { onClick: props.onClick as () => void }, props.children),
  };
});
vi.mock("@mantine/notifications", () => ({ notifications: { show: vi.fn() } }));

vi.mock("@tabler/icons-react", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const icon = () => () => R.createElement("span");
  return { IconArrowRight: icon(), IconBrain: icon(), IconCheck: icon(), IconPlus: icon() };
});

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
vi.mock("@/lib/hooks", () => ({
  useUserSettings: () => ({ data: mockSettings, isLoading: false }),
}));

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
  it("renders enquiry textarea with submit button", () => {
    renderPage();
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument();
    expect(screen.getByLabelText("Start consensus")).toBeInTheDocument();
  });

  it("pre-selects default models from user settings", () => {
    renderPage();
    // Default models m1 and m2 should appear as pills (and also in popover)
    expect(screen.getAllByText("GPT-4o").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Claude 3").length).toBeGreaterThanOrEqual(1);
    // Verify pills have remove buttons (indicating they are selected pills)
    const removeButtons = screen.getAllByLabelText("Remove");
    expect(removeButtons.length).toBe(2);
  });

  it("shows all models in popover grouped by provider", () => {
    renderPage();
    // Provider groups should show
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();
    // All models listed in popover
    expect(screen.getByText("GPT-4o Mini")).toBeInTheDocument();
  });

  it("disables submit when enquiry is empty", () => {
    renderPage();
    const submit = screen.getByLabelText("Start consensus");
    expect(submit).toBeDisabled();
  });
});
