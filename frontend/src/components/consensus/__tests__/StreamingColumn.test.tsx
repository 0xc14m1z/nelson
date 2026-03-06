import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";
import type { ModelStreamState } from "@/hooks/useConsensusStream";

// Mock @mantine/core with lightweight components to avoid OOM from emotion CSS-in-JS
vi.mock("@mantine/core", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  return {
    Alert: (props: Record<string, unknown>) =>
      R.createElement("div", { role: "alert" }, props.title, props.children),
    Badge: (props: Record<string, unknown>) => R.createElement("span", null, props.children),
    Box: (props: Record<string, unknown>) =>
      R.createElement(props.component === "span" ? "span" : "div", null, props.children),
    Group: wrap(),
    Loader: () => R.createElement("span", null, "Loading..."),
    Paper: wrap(),
    ScrollArea: (props: Record<string, unknown>) => R.createElement("div", null, props.children),
    Text: wrap(),
  };
});

vi.mock("@tabler/icons-react", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  const icon = () => () => R.createElement("span");
  return { IconAlertTriangle: icon(), IconCheck: icon() };
});

vi.mock("../MarkdownContent", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const R = require("react");
  return {
    MarkdownContent: (props: { children: string }) =>
      R.createElement("div", null, props.children),
  };
});

import { StreamingColumn } from "../StreamingColumn";

const baseModel: ModelStreamState = {
  llm_model_id: "model-1",
  round_number: 1,
  role: "responder",
  text: "",
  isStreaming: false,
  isDone: false,
  error: null,
  structured: {},
  input_tokens: 0,
  output_tokens: 0,
  cost: 0,
  duration_ms: 0,
};

describe("StreamingColumn", () => {
  it("renders model display name", () => {
    render(
      <StreamingColumn model={baseModel} displayName="openai/gpt-4o" allModelsDone={false} />,
    );
    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
  });

  it("shows streaming text with cursor", () => {
    const model: ModelStreamState = { ...baseModel, text: "Hello world", isStreaming: true };
    render(
      <StreamingColumn model={model} displayName="test-model" allModelsDone={false} />,
    );
    expect(screen.getByText("Hello world")).toBeInTheDocument();
    expect(screen.getByText("|")).toBeInTheDocument();
  });

  it("shows Done badge when complete", () => {
    const model: ModelStreamState = { ...baseModel, text: "Result", isDone: true };
    render(
      <StreamingColumn model={model} displayName="test-model" allModelsDone={true} />,
    );
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows waiting message when done but others streaming", () => {
    const model: ModelStreamState = { ...baseModel, text: "Result", isDone: true };
    render(
      <StreamingColumn model={model} displayName="test-model" allModelsDone={false} />,
    );
    expect(screen.getByText("Waiting for other models to finish...")).toBeInTheDocument();
  });

  it("shows error with alert", () => {
    const model: ModelStreamState = {
      ...baseModel,
      isDone: true,
      error: "timeout after 60s",
    };
    render(
      <StreamingColumn model={model} displayName="test-model" allModelsDone={false} />,
    );
    expect(screen.getByText("timeout after 60s")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("hides cursor when not streaming", () => {
    const model: ModelStreamState = { ...baseModel, text: "Some text", isStreaming: false };
    render(
      <StreamingColumn model={model} displayName="test-model" allModelsDone={false} />,
    );
    expect(screen.getByText("Some text")).toBeInTheDocument();
    expect(screen.queryByText("|")).not.toBeInTheDocument();
  });
});
