# Nelson

Nelson is a Python 3.14+ CLI-first agent for multi-model LLM orchestration.

It accepts one user prompt, sends it to multiple participant models through OpenRouter, and uses a separate moderator model to drive iterative synthesis toward the best answer available.

## Status

This repository currently contains the v1 design, protocol, schema, CLI, prompt, and testing specifications.

Implementation has not started yet.

## v1 Scope

Nelson v1 is designed to provide:

- a CLI with `auth` and `run`
- a headless orchestration core
- OpenRouter as the only provider
- a typed event stream
- `human`, `--json`, and `--jsonl` output modes
- a structured consensus workflow with multiple participants and one moderator

Out of scope for v1:

- multi-turn memory
- persisted run history
- multiple providers
- external prompt files for internal system prompts
- project-local `.nelson/`
- attachments or arbitrary extra context files

## Planned CLI Surface

```bash
nelson auth set --api-key <KEY>
nelson auth status
nelson auth clear
nelson run ...
```

## Documentation Map

Start here:

1. [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md)
2. [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)

Normative specifications:

- [`docs/APPLICATION_PROTOCOL.md`](./docs/APPLICATION_PROTOCOL.md)
- [`docs/EVENT_SCHEMA.md`](./docs/EVENT_SCHEMA.md)
- [`docs/RUN_RESULT_SCHEMA.md`](./docs/RUN_RESULT_SCHEMA.md)
- [`docs/CLI_SPEC.md`](./docs/CLI_SPEC.md)
- [`docs/PROMPT_SPEC.md`](./docs/PROMPT_SPEC.md)
- [`docs/ACCEPTANCE_TESTS.md`](./docs/ACCEPTANCE_TESTS.md)

Visual flow reference:

- [`docs/FLOWS.md`](./docs/FLOWS.md)

Engineering and tooling:

- [`docs/PYTHON_ENGINEERING_STANDARDS.md`](./docs/PYTHON_ENGINEERING_STANDARDS.md)
- [`docs/PYPROJECT_TOOLING_SPEC.md`](./docs/PYPROJECT_TOOLING_SPEC.md)

Implementation guidance:

- [`docs/CODING_AGENT_HANDOFF.md`](./docs/CODING_AGENT_HANDOFF.md)
- [`docs/OPUS_PREPLAN.md`](./docs/OPUS_PREPLAN.md)

## Core Design Principles

- Keep the orchestration core headless.
- Keep the CLI thin.
- Preserve a typed command/event boundary between adapters and core.
- Keep public JSON and event contracts stable.
- Keep workflow artifacts strongly typed and validated.
- Keep OpenRouter details isolated in provider code.
- Prefer deterministic tests and fake-provider coverage before live integration.

## Intended Implementation Order

1. Bootstrap the Python project and package layout.
2. Implement `auth`.
3. Implement the typed application protocol and core result/event contracts.
4. Add the OpenRouter adapter.
5. Deliver the first visible `run` happy path with `human`, `--json`, and `--jsonl`.
6. Harden failure handling, repair, reframing, and release-gate behavior.

## Repository Description

Suggested GitHub repository description:

> CLI-first Python agent for typed multi-model LLM orchestration with moderator-driven consensus.
