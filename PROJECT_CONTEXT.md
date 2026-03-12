# Nelson Project Context

## What Nelson Is

Nelson is a Python 3.14+ CLI-first agent for multi-model LLM orchestration.

It takes one user prompt, sends it to multiple participant models through OpenRouter, and uses a separate moderator model to drive iterative synthesis toward the best answer available.

Nelson is not a generic chatbot wrapper. Its core identity is:

- multi-model orchestration
- moderator-driven synthesis
- command/event protocol boundary between adapters and core
- typed internal workflow artifacts
- strongly typed event stream
- agent-friendly CLI

## v1 Goal

Deliver a one-shot CLI and headless orchestration core that:

- supports `auth` and `run`
- uses OpenRouter as the only provider
- streams typed events
- supports human, `--json`, and `--jsonl` outputs
- runs a structured consensus workflow with participants and a moderator

## v1 Non-Goals

Do not implement these unless explicitly requested later:

- multi-turn memory
- persisted run history
- `inspect`
- profiles
- external system prompt files
- project-local `.nelson/`
- additional providers
- attachments or arbitrary extra context files

## Read This Next

Any coding agent starting work should read these documents in this order:

1. [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)
2. [docs/APPLICATION_PROTOCOL.md](./docs/APPLICATION_PROTOCOL.md)
3. [docs/CODING_AGENT_HANDOFF.md](./docs/CODING_AGENT_HANDOFF.md)
4. [docs/PYTHON_ENGINEERING_STANDARDS.md](./docs/PYTHON_ENGINEERING_STANDARDS.md)
5. [docs/PYPROJECT_TOOLING_SPEC.md](./docs/PYPROJECT_TOOLING_SPEC.md)
6. [docs/CLI_SPEC.md](./docs/CLI_SPEC.md)
7. [docs/EVENT_SCHEMA.md](./docs/EVENT_SCHEMA.md)
8. [docs/RUN_RESULT_SCHEMA.md](./docs/RUN_RESULT_SCHEMA.md)
9. [docs/PROMPT_SPEC.md](./docs/PROMPT_SPEC.md)
10. [docs/ACCEPTANCE_TESTS.md](./docs/ACCEPTANCE_TESTS.md)

## Non-Negotiable Rules

- Keep the orchestration core headless.
- Keep the CLI thin.
- Keep a typed command/event boundary between adapters and core.
- Keep OpenRouter details isolated in provider code.
- Keep event and JSON contracts stable.
- Keep internal workflow outputs typed and validated.
- Keep fake-provider testing mandatory.
- Keep observability compatible with optional Logfire integration.

## Implementation Starting Point

If the repository is still implementation-empty, start here:

1. create `pyproject.toml`
2. initialize the `src/nelson/` package
3. wire the `nelson` CLI entrypoint
4. implement `auth`
5. define typed schemas before building orchestration

## Decision Rule

If a detail is not fully specified, choose the simplest implementation that:

- preserves the documented public contracts
- does not widen v1 scope
- keeps typing, testing, and observability strong
