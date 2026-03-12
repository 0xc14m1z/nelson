# Coding Agent Handoff for Nelson v1

## Purpose

This document tells a coding agent exactly how to approach Nelson v1 implementation.

It is not a product overview. It is an execution guide:

- what to read first
- what to implement first
- what constraints are non-negotiable
- what to defer
- how to decide between acceptable implementation choices

## Intended Reader

This document is written primarily for Claude or any coding agent implementing Nelson from the current repository state.

## Current Repository State

At the time of writing:

- the repository contains specifications and planning documents
- the repository does not yet contain the actual Nelson implementation
- the implementation is expected to be built from these documents

## Normative References

Read these documents in the order listed below.

1. [../PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md)
2. [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
3. [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
4. [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)
5. [PYPROJECT_TOOLING_SPEC.md](./PYPROJECT_TOOLING_SPEC.md)
6. [CLI_SPEC.md](./CLI_SPEC.md)
7. [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
8. [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
9. [PROMPT_SPEC.md](./PROMPT_SPEC.md)
10. [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)

If any local implementation decision conflicts with one of these files, those files take precedence over convenience.

## 1. Implementation Objective

Implement Nelson v1 as:

- a Python 3.14+ project
- a headless async orchestration core
- a CLI first interface
- an OpenRouter-backed multi-model consensus system
- a strongly typed event-driven runtime

Do not widen scope beyond v1.

## 2. Non-Negotiable Constraints

The following constraints must be preserved.

### 2.1 Architecture

- The orchestration core must remain headless.
- The CLI must remain a thin adapter over the core.
- Adapters must communicate with the core only through typed application commands and typed events.
- The provider abstraction must remain small.
- OpenRouter-specific logic must stay isolated in provider code.
- Event emission must be a first-class core behavior.

### 2.2 Typing

- Internal workflow artifacts must be schema-driven.
- Event payloads must be strongly typed.
- Final JSON output must match the documented schema.
- Do not use loose untyped dicts as core domain objects.

### 2.3 Consensus

- Task framing is mandatory.
- Moderator and participant roles must remain distinct.
- Participant review must be anonymized.
- Blocking review states are `major_revise` and `reject`.
- Max-round exhaustion must return a partial result if a usable answer exists.

### 2.4 Scope

Do not implement these in v1 unless explicitly instructed later:

- multi-turn conversations
- persisted run history
- `inspect`
- profiles
- external system prompt files
- project-local `.nelson/`
- additional providers
- attachments or arbitrary extra context files

## 3. Reading and Implementation Order

The recommended order is deliberate. Follow it unless there is a concrete reason not to.

### Step 1: Create project scaffolding

Read first:

- [PYPROJECT_TOOLING_SPEC.md](./PYPROJECT_TOOLING_SPEC.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)

Implement:

- `pyproject.toml`
- `uv` project initialization
- package skeleton under `src/nelson/`
- tests package skeleton
- console entrypoint for `nelson`
- base tooling configuration for Ruff, Pyright, pytest, coverage

Exit condition:

- the project installs
- `uv run nelson --help` works
- lint/type/test tooling commands exist

### Step 2: Implement credential storage and auth CLI

Read first:

- [CLI_SPEC.md](./CLI_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)

Implement:

- `auth set`
- `auth status`
- `auth clear`
- `~/.nelson/` creation
- credential resolution policy

Exit condition:

- auth commands behave per spec
- saved-key behavior is testable using temporary `HOME`

### Step 3: Implement typed protocols before orchestration

Read first:

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)

Implement:

- application command models
- application dispatcher protocol
- event envelope model
- event payload models
- run result model
- task framing model
- participant contribution model
- review model
- release gate model
- structured error model

Exit condition:

- commands and events are both strongly typed
- JSON Schema export works
- all schema examples validate

Do not postpone this step. The rest of the system depends on these types.

### Step 4: Implement provider abstraction and OpenRouter adapter

Read first:

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)

Implement:

- provider interface
- OpenRouter request execution
- OpenRouter streaming support
- usage extraction where available
- timeout handling
- retry integration points

Exit condition:

- one invocation can run in non-streaming mode
- one invocation can stream deltas
- provider failures map to typed errors

### Step 5: Implement the core event stream machinery

Read first:

- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)

Implement:

- run-scoped event emission
- monotonic `sequence`
- run/event/invocation ids
- helpers for emitting typed events
- ordered stream abstraction consumable by CLI renderers

Exit condition:

- a simple synthetic run can emit a valid ordered JSONL event stream

### Step 6: Implement consensus workflow

Read first:

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)

Implement:

- moderator task framing
- participant initial contribution round
- moderator synthesis
- participant review
- blocking rules
- early stop
- partial result on max-round exhaustion

Exit condition:

- mock-provider tests can cover success, multi-round revise, and partial consensus paths

### Step 7: Implement release gate, repair, and failure policies

Read first:

- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)

Implement:

- release gate flow
- one repair attempt for invalid structured output
- one retry path where applicable
- quorum enforcement
- moderator failure handling

Exit condition:

- failure/repair acceptance tests pass

### Step 8: Implement CLI rendering modes

Read first:

- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)

Implement:

- human renderer
- JSON renderer
- JSONL renderer
- stdout/stderr discipline
- correct exit code behavior

Exit condition:

- machine-readable modes are clean
- human mode is concise and informative

### Step 9: Add observability integration

Read first:

- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)

Implement:

- optional Logfire setup
- HTTPX instrumentation
- Pydantic instrumentation
- manual spans around model calls and consensus phases

Exit condition:

- code works with and without Logfire configuration

This should not distort the core architecture. Observability wraps the system; it does not redefine it.

### Step 10: Validate against acceptance tests

Read first:

- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)

Implement or verify:

- schema tests
- CLI validation tests
- auth tests
- event tests
- consensus tests
- failure and repair tests
- output mode tests

Exit condition:

- the minimum definition of done is met

## 4. Design Decision Rules

When multiple acceptable implementations exist, use these decision rules.

### 4.1 Prefer explicitness

Prefer:

- typed models over free-form mappings
- explicit helpers over clever abstractions
- small interfaces over “generic” frameworks

Avoid:

- unnecessary inversion layers
- speculative extensibility
- hidden stateful magic

### 4.2 Prefer stable contracts over convenience

If there is tension between a faster implementation and a cleaner contract:

- prioritize stable event contracts
- prioritize stable CLI behavior
- prioritize stable error semantics

### 4.3 Prefer deterministic tests over live integration

If a behavior can be tested with a fake provider, do that first.

Live provider calls are useful for smoke coverage, not as the foundation of the suite.

### 4.4 Prefer local validation over blind trust in provider features

Even if OpenRouter supports structured output features:

- still validate locally
- still map failures into domain errors
- still preserve repair logic

## 5. Specific Anti-Patterns to Avoid

Do not introduce any of the following unless explicitly approved later:

- orchestration logic inside CLI command functions
- provider-specific response parsing scattered across core logic
- untyped event payload dicts
- multiple competing output paths that bypass the shared event model
- hidden fallback behavior that changes semantics without emitting events
- storing run history in v1
- adding config systems beyond what is already specified
- exact-pin sprawl in `pyproject.toml`
- dependency overlap such as Black plus Ruff or mypy plus Pyright

## 6. Testing Priorities

When time is limited, testing priority order is:

1. schema validation and serialization
2. CLI argument validation
3. consensus flow with fake provider
4. failure and repair behavior
5. output-mode correctness
6. live OpenRouter smoke tests

Do not skip fake-provider tests in order to get to live tests faster.

## 7. Handoff-Friendly Deliverables

By the time implementation is considered meaningfully underway, the repository should contain:

- `pyproject.toml`
- `uv.lock`
- `src/nelson/...`
- `tests/...`
- initial `pre-commit` configuration
- a working `nelson` CLI entrypoint

By the time v1 is considered feature-complete, it should also contain:

- typed event models
- typed result models
- auth commands
- run command
- OpenRouter adapter
- consensus engine
- repair and release gate logic
- acceptance tests aligned with the spec set

## 8. What to Do if Specs Feel Slightly Incomplete

If a small implementation detail is not fully specified:

1. choose the simplest option that preserves all existing contracts
2. document the choice in code or a short note
3. do not widen scope
4. do not break any normative document

If a choice would alter public CLI, event, or JSON contracts, stop and request clarification instead of guessing.

## 9. Suggested First Implementation Session

If starting from an empty repository, the first useful session should produce:

- `pyproject.toml`
- `src/nelson/__init__.py`
- `src/nelson/main.py`
- `src/nelson/cli/app.py`
- `src/nelson/cli/auth.py`
- `src/nelson/cli/run.py`
- `tests/`
- baseline tool configuration

This is the correct first slice because it creates a runnable shell for all later work.

## 10. Final Reminder

Nelson is not a generic chatbot wrapper.

Its essential product identity is:

- multi-model orchestration
- moderator-driven synthesis
- reusable command/event boundary
- typed internal workflow
- reusable event stream
- agent-friendly CLI

If an implementation choice weakens one of those properties, it is probably the wrong choice.

## 11. References

1. [../PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md)
2. [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
3. [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
4. [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)
5. [PYPROJECT_TOOLING_SPEC.md](./PYPROJECT_TOOLING_SPEC.md)
6. [CLI_SPEC.md](./CLI_SPEC.md)
7. [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
8. [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
9. [PROMPT_SPEC.md](./PROMPT_SPEC.md)
10. [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)
