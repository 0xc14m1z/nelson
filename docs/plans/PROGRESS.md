# Nelson v1 Implementation Progress

This file is updated at the end of each phase to track progress across sessions.
Each session starts by reading this file and running the verification command for the last completed phase.

## Phase Status

| Phase | Status | Date | Verification |
| --- | --- | --- | --- |
| 1. Project Scaffold | complete | 2026-03-13 | 41 tests pass, pyright 0 errors, ruff clean |
| 2. Typed Contracts | complete | 2026-03-13 | 41 tests pass, pyright 0 errors, ruff clean |
| 3. Auth & Credentials | complete | 2026-03-13 | 69 tests pass, pyright 0 errors, ruff clean |
| 4. Provider & Fake | complete | 2026-03-13 | 82 tests pass, pyright 0 errors, ruff clean |
| 5. Event Machinery & CLI Validation | not started | | |
| 6. Happy-Path Consensus (demo checkpoint) | not started | | |
| 7. Multi-Round & Framing Updates | not started | | |
| 8. Retry, Repair & Failure | not started | | |
| 9. Observability & Progress | not started | | |
| 10. Validation & Release Readiness | not started | | |
| 11. Structured Logging & Observability | not started | | |

## How to Use This File

### Starting a new session

1. Read this file to see which phase was last completed.
2. Run the verification command from the **next** phase's "Session start" section in `IMPLEMENTATION_PHASES.md`.
3. If verification passes, proceed with that phase's TDD cycle.
4. If verification fails, diagnose and fix before starting new work.

### Completing a phase

Update the table above with:
- **Status:** `complete`
- **Date:** the date of completion
- **Verification:** the command output or a summary confirming exit criteria were met

### Notes per phase

Add notes below as phases complete. Record any decisions made under spec ambiguity, test count, or deviations from the plan.

---

## Phase Notes

### Phase 1+2: Project Scaffold + Typed Contracts (2026-03-13)

Combined into one session per plan recommendation. PR #1.

- 41 tests: 4 CLI help + 4 commands + 33 events (parametrized discriminated union + structural guards)
- Redundant domain and result model tests removed during review — those models are tested indirectly through events/results or will be tested when agents consume them
- Added `Adapter` enum (reviewer feedback) — only `cli` for v1, type-safe and extensible
- All classes, functions, and Pydantic fields documented with docstrings and `Field(description=...)`

### Phase 3: Auth & Credentials (2026-03-13)

PR #2. 69 tests (28 new auth tests).

- CLI auth commands: `nelson auth set`, `nelson auth status`, `nelson auth clear`
- Credential resolution chain: CLI override → env var → saved key file
- Event-driven protocol: dispatcher emits typed events, CLI consumes
- `CommandFailedPayload` with typed `error` field for structured error reporting

### Phase 4: Provider & Fake (2026-03-13)

13 new tests (8 fake provider + 3 protocol conformance + 2 error hierarchy), 3 live tests (skipped without API key).

- `Provider` Protocol with `invoke()` (non-streaming) and `stream()` (SSE streaming)
- `FakeProvider` with queued responses, stream deltas, and error simulation for all failure modes
- `OpenRouterProvider` with httpx: non-streaming invoke, lazy SSE streaming via `_LazyOpenRouterStream`
- Domain error hierarchy: `NelsonError` base → `ProviderTimeoutError`, `ProviderTransportError`, `ProviderAuthError`, `StructuredOutputInvalidError`
- Each error maps to `ErrorCode` enum via class attribute
- Merged `_ErrorStream` into `FakeStream` (simplify review)
- Extracted `_auth_headers()` helper to eliminate header duplication
- Type-safe usage extraction with `isinstance` guards (no `type: ignore`)
