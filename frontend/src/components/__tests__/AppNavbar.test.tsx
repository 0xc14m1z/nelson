import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";

const mockPush = vi.fn();
const mockLogout = vi.fn().mockResolvedValue(undefined);

const { mockSessions } = vi.hoisted(() => ({
  mockSessions: [
    {
      id: "s1",
      enquiry: "What is the meaning of life?",
      status: "consensus_reached",
      model_ids: ["m1"],
      current_round: 3,
      total_cost: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_duration_ms: 0,
      max_rounds: null,
      created_at: "2026-03-01T00:00:00Z",
      completed_at: null,
    },
    {
      id: "s2",
      enquiry: "Explain quantum computing",
      status: "responding",
      model_ids: ["m1", "m2"],
      current_round: 1,
      total_cost: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_duration_ms: 0,
      max_rounds: null,
      created_at: "2026-03-02T00:00:00Z",
      completed_at: null,
    },
  ],
}));

let currentSessions = mockSessions;

vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  return {
    Button: (props: Record<string, unknown>) =>
      R.createElement("button", { onClick: props.onClick }, props.children),
    ScrollArea: wrap(),
    Text: wrap(),
    Title: (props: Record<string, unknown>) =>
      R.createElement(`h${props.order || 1}`, { onClick: props.onClick, style: props.style }, props.children),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/",
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ logout: mockLogout }),
}));

vi.mock("@/lib/hooks", () => ({
  useSessions: () => ({ data: currentSessions }),
}));

vi.mock("@tabler/icons-react", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  return {
    IconSettings: (props: Record<string, unknown>) => R.createElement("svg", props),
    IconLogout: (props: Record<string, unknown>) => R.createElement("svg", props),
  };
});

import { AppNavbar } from "../AppNavbar";

describe("AppNavbar", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockLogout.mockClear().mockResolvedValue(undefined);
    currentSessions = mockSessions;
  });

  it("renders Nelson logo", () => {
    render(<AppNavbar />);
    expect(screen.getByText("Nelson")).toBeInTheDocument();
  });

  it("renders New Session button", () => {
    render(<AppNavbar />);
    expect(screen.getByText("New Session")).toBeInTheDocument();
  });

  it("renders session entries", () => {
    render(<AppNavbar />);
    expect(screen.getByText("What is the meaning of life?")).toBeInTheDocument();
    expect(screen.getByText("Explain quantum computing")).toBeInTheDocument();
  });

  it("renders Settings and Logout in footer", () => {
    render(<AppNavbar />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("navigates to /sessions/new on button click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("New Session"));
    expect(mockPush).toHaveBeenCalledWith("/sessions/new");
  });

  it("navigates to session on click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("What is the meaning of life?"));
    expect(mockPush).toHaveBeenCalledWith("/sessions/s1");
  });

  it("navigates to /settings on click", () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("Settings"));
    expect(mockPush).toHaveBeenCalledWith("/settings");
  });

  it("calls logout and redirects to /login", async () => {
    render(<AppNavbar />);
    fireEvent.click(screen.getByText("Logout"));
    expect(mockLogout).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
  });

  it("shows pulsing dot for active sessions only", () => {
    const { container } = render(<AppNavbar />);
    const dots = container.querySelectorAll("[class*='activeDot']");
    expect(dots).toHaveLength(1);
  });

  it("shows empty state when no sessions", () => {
    currentSessions = [];
    render(<AppNavbar />);
    expect(screen.getByText("No sessions yet")).toBeInTheDocument();
  });

  it("calls onNavigate callback on navigation", () => {
    const onNavigate = vi.fn();
    render(<AppNavbar onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("Settings"));
    expect(onNavigate).toHaveBeenCalled();
  });
});
