# Python Engineering Standards for Nelson

## Purpose

This document defines the engineering standards for Python code in Nelson.

It has two goals:

- establish general high-quality Python development rules
- define how those rules apply concretely to Nelson as an async, typed, event-driven LLM orchestration system

This document is written for humans and coding agents. It is intentionally normative and specific.

## Normative Language

The keywords below are used intentionally:

- `MUST`: mandatory rule
- `SHOULD`: strong default that may be overridden with explicit justification
- `MAY`: acceptable option

## Normative References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [PYPROJECT_TOOLING_SPEC.md](./PYPROJECT_TOOLING_SPEC.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)
- Python 3.14 documentation: <https://docs.python.org/3.14/>
- What's New In Python 3.14: <https://docs.python.org/3.14/whatsnew/3.14.html>
- uv: <https://docs.astral.sh/uv/>
- Ruff: <https://docs.astral.sh/ruff/>
- Pyright: <https://github.com/microsoft/pyright>
- pytest: <https://docs.pytest.org/en/stable/>
- pytest-asyncio: <https://pytest-asyncio.readthedocs.io/en/stable/>
- coverage.py: <https://coverage.readthedocs.io/>
- pre-commit: <https://pre-commit.com/>
- Pydantic: <https://docs.pydantic.dev/>
- Pydantic Logfire: <https://logfire.pydantic.dev/docs/>

## 1. Project Baseline

### 1.1 Python version

- Nelson `MUST` target `Python 3.14+`.
- Nelson `MAY` use the newest stable Python 3.14 features freely.
- Nelson `MUST NOT` carry compatibility shims for older Python versions unless the project explicitly changes policy later.

### 1.2 Toolchain

Nelson `MUST` standardize on this toolchain:

- `uv` for environment and dependency management
- `ruff` for linting, formatting, and import ordering
- `pyright` in `strict` mode for type checking
- `pytest` for tests
- `pytest-asyncio` for async tests
- `coverage.py` for coverage reporting
- `pre-commit` for local hook orchestration
- `pydantic v2` for schema validation and JSON Schema export
- `pydantic logfire` as an optional observability integration

Nelson `MUST NOT` add overlapping tools without a strong project-level reason.

Examples of overlap to avoid:

- adding Black when Ruff formatting is already adopted
- adding mypy when Pyright is the fixed type checker
- adding ad hoc shell scripts for workflows already covered by `uv`

### 1.3 Source layout

- The project `MUST` use a `src/` layout.
- The CLI entrypoint `MUST` live inside the package, not as a loose root script.
- Tool configuration `MUST` be centralized in `pyproject.toml`.
- Top-level repository scripts `SHOULD` be rare and justified.

## 2. Core Engineering Principles

### 2.1 Clarity over cleverness

- Code `MUST` optimize for readability and maintainability over clever compactness.
- Public code paths `SHOULD` be easy to follow without hidden side effects.
- Unusual patterns `MUST` carry a short rationale in code comments or nearby documentation.

### 2.2 Explicit contracts

- Inputs and outputs at system boundaries `MUST` be explicit and validated.
- Core contracts `MUST` be represented through typed models, not informal dictionaries.
- The more central a contract is to orchestration, the stronger its typing must be.

### 2.3 Small responsibilities

- Modules `MUST` have narrow responsibilities.
- Functions `SHOULD` do one thing well.
- Components `MUST NOT` mix orchestration, I/O, validation, rendering, and storage concerns in the same layer.

### 2.4 Deterministic behavior

- Code `MUST` fail deterministically where possible.
- Retry, timeout, and fallback behavior `MUST` be centralized and discoverable.
- Hidden retries or silent degradation `MUST NOT` exist in core logic.

## 3. Architecture and Separation of Concerns

### 3.1 Mandatory boundaries

Nelson `MUST` preserve a clear separation between:

- CLI
- application protocol boundary
- orchestration core
- consensus logic
- provider adapters
- prompt construction
- typed protocols and schemas
- storage and credentials
- rendering

### 3.2 Boundary rules

- The CLI `MUST NOT` contain orchestration logic.
- Adapters `MUST` call the core through typed application commands.
- Adapters `MUST NOT` reach into core internals directly.
- Provider adapters `MUST NOT` contain consensus logic.
- Prompt modules `MUST NOT` contain transport logic.
- Rendering modules `MUST NOT` decide orchestration policy.
- Storage modules `MUST NOT` reach into CLI-specific presentation concerns.

### 3.3 Nelson-specific application

For Nelson specifically:

- the command/event application protocol is a public internal architecture contract
- the event stream is a core product contract
- the provider abstraction is intentionally small
- the moderator/participant workflow is domain logic, not CLI logic
- OpenRouter-specific details must stay in provider code

## 4. Typing and Data Modeling

### 4.1 Type coverage

- All public functions, methods, and module-level constants `MUST` be typed.
- Internal helpers `SHOULD` also be typed unless they are extremely local and obvious.
- New code `MUST NOT` introduce untyped public interfaces.

### 4.2 `Any` policy

- `Any` `MUST NOT` be used in domain models, event payloads, consensus logic, or CLI contracts.
- `Any` `MAY` appear only at untyped external library boundaries and should be wrapped immediately into typed local objects.
- `dict[str, Any]` `MUST NOT` be the default representation for meaningful internal data.

### 4.3 Preferred modeling tools

- Use `Pydantic models` for validated runtime contracts and external data boundaries.
- Use `Protocol` for behavioral interfaces.
- Use `TypedDict` only when a lightweight mapping contract is clearly the right fit.
- Use `Literal`, `Enum`, or `StrEnum` where a closed value set exists.
- Use `dataclass` only for simple internal value objects that do not need runtime validation.

### 4.4 Model design rules

- Models `SHOULD` prefer explicit field names over clever abbreviations.
- Optionality `MUST` be semantically justified.
- Default values `MUST` be meaningful and safe.
- Mutable defaults `MUST NOT` be used.
- Model validation `SHOULD` happen at boundaries, not repeatedly in the middle of business logic.

### 4.5 Nelson-specific application

Nelson `MUST` use strong models for at least:

- event envelope and event payloads
- task framing
- participant initial contribution
- participant review result
- release gate result
- final run result
- structured error objects

## 5. Async and Concurrency

### 5.1 General policy

- Async code `MUST` exist where the system is fundamentally I/O-bound or orchestration-bound.
- Async code `MUST NOT` spread into pure transformation logic unnecessarily.
- Synchronous pure functions `SHOULD` remain synchronous.

### 5.2 Concurrency ownership

- Every spawned concurrent task `MUST` have an explicit owner.
- Fire-and-forget tasks `MUST NOT` exist in production logic.
- Cancellation behavior `MUST` be explicit.
- Timeouts `MUST` be enforced at the call boundary, not left implicit.

### 5.3 Preferred primitives

- Prefer `asyncio.TaskGroup` over unmanaged `create_task` patterns.
- Prefer structured concurrency over ad hoc task tracking.
- Shared mutable state across tasks `MUST` be minimized.

### 5.4 Nelson-specific application

For Nelson specifically:

- participant model calls `MUST` run concurrently where intended
- event emission `MUST` still preserve a total ordered stream
- consensus logic `SHOULD` remain mostly sync and deterministic around async call results
- retry, timeout, and repair behavior `MUST` remain observable and testable

## 6. Error Handling and Recovery

### 6.1 Exception policy

- Broad `except Exception` blocks `MUST NOT` exist unless they immediately re-raise or translate to a typed domain error with preserved context.
- Errors `MUST` be classified, not swallowed.
- Domain errors `SHOULD` have project-specific exception types.

### 6.2 Translation policy

- Internal errors `MUST` be translatable into structured CLI, event, and JSON errors.
- Human-readable messages `SHOULD` remain short and actionable.
- Machine-readable codes `MUST` be stable once published.

### 6.3 Retry policy

- Retry behavior `MUST` be centralized and bounded.
- Retries `MUST NOT` be hidden inside deep helper functions without visibility.
- Retry attempts `SHOULD` be reflected in events or logs where relevant.

### 6.4 Nelson-specific application

Nelson `MUST` clearly distinguish at least:

- invalid arguments
- credential errors
- provider auth errors
- provider transport or timeout errors
- participant failure
- moderator failure
- quorum loss
- structured output invalidity
- structured output repair failure

## 7. Observability and Logfire

### 7.1 Core principle

Observability is part of the design, not an afterthought.

### 7.2 Logging rules

- Core logic `MUST NOT` use `print()`.
- Domain events `MUST` be the primary runtime observability channel.
- Technical logs `SHOULD` be structured when emitted.
- Secrets `MUST NEVER` appear in logs, events, or exception messages.

### 7.3 Correlation identifiers

At minimum, the system `MUST` propagate and log where applicable:

- `run_id`
- `event_id`
- `invocation_id`
- `candidate_id`
- `sequence`

### 7.4 Logfire policy

- Logfire support `MUST` be designed in.
- Logfire exporting `MUST` be optional.
- The code `MUST` run correctly when Logfire is disabled or unconfigured.
- Logfire instrumentation `SHOULD` cover:
  - Pydantic validation
  - HTTPX client activity
  - manual spans around LLM invocations
  - manual spans around consensus rounds and release gate

### 7.5 Nelson-specific application

Nelson `MUST` be able to support future cloud log draining without redesigning its observability model.

That means:

- stable identifiers
- stable event contracts
- structured metadata
- no dependence on one specific backend

## 8. Testing Strategy

### 8.1 Layered testing

The project `MUST` use a layered test strategy:

- unit tests for pure logic and schema validation
- integration tests with a deterministic fake or mock provider
- limited live smoke tests with real providers

### 8.2 Real-model dependency policy

- Most tests `MUST NOT` depend on real LLMs.
- The majority of the suite `MUST` be deterministic.
- Live smoke tests `SHOULD` be opt-in or separately marked.

### 8.3 Async tests

- Async code `MUST` be tested with `pytest-asyncio`.
- Async failure paths `MUST` be tested explicitly, not inferred.
- Cancellation, timeout, retry, and repair paths `SHOULD` have dedicated tests.

### 8.4 Nelson-specific application

Nelson `MUST` have a fake provider capable of simulating:

- successful structured responses
- streamed deltas
- invalid JSON
- repair success and repair failure
- timeout
- transport failure
- participant dropout
- moderator failure

The fake provider is not optional. It is part of the design.

## 9. CLI and UX Stability

### 9.1 Stability rule

- CLI flags and output contracts `MUST` be treated as public interfaces once introduced.
- Human-readable output may evolve, but `--json` and `--jsonl` contracts `MUST` stay stable or be versioned.

### 9.2 Output discipline

- Machine-readable modes `MUST` avoid human noise on `stdout`.
- Human mode `SHOULD` remain concise and legible.
- Exit codes `MUST` remain stable and documented.

### 9.3 Nelson-specific application

Because Nelson is intended for use by agents:

- command intent must be explicit
- arguments must be validated strictly
- adapters must map cleanly onto typed commands
- output mode behavior must be predictable

## 10. Packaging and Project Layout

### 10.1 Repository structure

- Use `src/` layout.
- Keep package code inside `src/nelson/`.
- Keep tests outside the package in a dedicated tests tree.
- Avoid loose scripts in the repository root.

### 10.2 Configuration

- Tool configuration `MUST` live in `pyproject.toml` where practical.
- One-off tool configs `SHOULD` be justified.
- Runtime config `MUST NOT` be scattered across unrelated files.

### 10.3 Import policy

- Use absolute imports inside the package by default.
- Wildcard imports `MUST NOT` be used.
- Import ordering `MUST` be enforced by Ruff.
- Local imports inside functions `MUST` be rare and justified by a concrete need such as optional dependency loading or cycle avoidance.

## 11. Dependency Management

### 11.1 General policy

- Every dependency `MUST` have a clear reason to exist.
- Dependencies `SHOULD` be minimized.
- Overlapping dependencies `MUST NOT` accumulate casually.

### 11.2 Wrapper policy

- External SDKs and transport libraries `SHOULD` be wrapped behind local abstractions at meaningful boundaries.
- Business logic `MUST NOT` depend directly on provider SDK idiosyncrasies.

### 11.3 Nelson-specific application

For Nelson specifically:

- OpenRouter details belong in provider code
- HTTP clients belong in provider code
- event and consensus logic must not depend directly on raw provider response shapes

## 12. Documentation and Comments

### 12.1 Documentation rule

- Important architectural decisions `MUST` be documented.
- Public modules and non-obvious public classes or functions `SHOULD` have docstrings.
- Tiny helpers `MAY` rely on clear naming instead of redundant docstrings.

### 12.2 Comment rule

- Comments `SHOULD` explain why, not restate what the code already says.
- Temporary or workaround comments `MUST` be specific and actionable.
- Dead or stale comments `MUST NOT` remain in the codebase.

## 13. Python-Specific Do and Don't Rules

### 13.1 Do

- Use `pathlib` instead of manual path string manipulation.
- Use `StrEnum`, `Enum`, `Literal`, and typed constants where closed sets exist.
- Use `collections.abc` interfaces where appropriate.
- Use context managers for resources and scoped state.
- Use `f-strings` for readable interpolation.
- Use `Pydantic` or `dataclass` models instead of loose dictionaries for meaningful structures.
- Keep pure transformation code free of transport concerns.

### 13.2 Don't

- Do not use mutable default arguments.
- Do not rely on hidden module-level global state for runtime behavior.
- Do not pass untyped dictionaries through multiple layers.
- Do not bury important control flow in decorators or metaprogramming.
- Do not mix sync and async APIs casually in the same abstraction.
- Do not silently coerce invalid data when validation should fail explicitly.
- Do not duplicate schemas in multiple places.

## 14. Code Review Standards

Every substantive change `SHOULD` be reviewed against this checklist:

- Are boundaries between core, CLI, provider, prompt, and schema layers preserved?
- Are new public APIs fully typed?
- Are new data contracts modeled explicitly?
- Are error paths deterministic and observable?
- Is async ownership clear?
- Are tests present for the behavior that changed?
- Are logs and events free of secrets?
- Does the change preserve CLI and event contract stability?

## 15. Definition of Done

A change is not done until all of the following are true:

- formatting and linting pass
- strict type checking passes
- relevant tests pass
- new schemas validate
- new errors are mapped cleanly to structured outputs where required
- observability identifiers remain intact
- no secrets are exposed in logs or events
- documentation is updated when contracts or architecture change

## 16. Nelson-Specific Non-Negotiables

These rules are especially important and should be treated as hard constraints unless the project explicitly changes direction:

- The orchestration core must stay headless.
- The command/event boundary between adapters and core must stay explicit.
- The event stream must stay typed and stable.
- Internal workflow artifacts must be schema-driven.
- Provider details must stay isolated.
- Fake-provider testing is mandatory.
- Observability must work with or without Logfire export enabled.

## 17. Suggested Tooling Configuration Direction

These are recommended implementation defaults to match this standard:

- Ruff handles linting, formatting, and import ordering.
- Pyright runs in strict mode.
- `pytest-asyncio` is configured for the project's async model.
- `coverage.py` is used directly or through a thin test command wrapper.
- `pre-commit` runs Ruff, Pyright, and targeted test or validation hooks where practical.

The exact `pyproject.toml` values may be specified separately, but they should align with this document.

## 18. References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [PYPROJECT_TOOLING_SPEC.md](./PYPROJECT_TOOLING_SPEC.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)
- Python 3.14 documentation: <https://docs.python.org/3.14/>
- uv: <https://docs.astral.sh/uv/>
- Ruff: <https://docs.astral.sh/ruff/>
- Pyright: <https://github.com/microsoft/pyright>
- pytest: <https://docs.pytest.org/en/stable/>
- pytest-asyncio: <https://pytest-asyncio.readthedocs.io/en/stable/>
- coverage.py: <https://coverage.readthedocs.io/>
- pre-commit: <https://pre-commit.com/>
- Pydantic: <https://docs.pydantic.dev/>
- Pydantic Logfire: <https://logfire.pydantic.dev/docs/>
