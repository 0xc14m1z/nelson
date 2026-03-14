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
| 5. Event Machinery & CLI Validation | complete | 2026-03-14 | 100 tests pass, pyright 0 errors, ruff clean |
| 6. Happy-Path Consensus (demo checkpoint) | complete | 2026-03-14 | 122 tests pass, pyright 0 errors, ruff clean |
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
- `OpenRouterProvider` using the OpenAI Python SDK (`AsyncOpenAI` with `base_url` pointed at OpenRouter). SDK handles SSE parsing, typed response models, and connection lifecycle. Hidden retries disabled (`max_retries=0`) per §6.3.
- Domain error hierarchy: `NelsonError` base → `ProviderTimeoutError`, `ProviderTransportError`, `ProviderAuthError`, `StructuredOutputInvalidError`
- Each error maps to `ErrorCode` enum via class attribute
- SDK exceptions (`AuthenticationError`, `APITimeoutError`, `APIConnectionError`, `APIStatusError`) translated to domain errors via `_translate_error()`
- Merged `_ErrorStream` into `FakeStream` (simplify review)
- Removed trivial `test_core/test_errors.py` — error types are tested through provider and orchestration tests

### Phase 5: Event Machinery & CLI Validation (2026-03-14)

23 new tests (7 emitter + 5 ID generation + 11 CLI validation), 100 total.

- `EventEmitter` class: monotonic sequence numbering, unique `evt_`-prefixed IDs, UTC ISO 8601 timestamps, async iteration. Batch-collect design for Phase 5; streaming variant planned for Phase 6+.
- Centralized `utils/ids.py`: `make_run_id()`, `make_command_id()`, `make_invocation_id()`, `make_candidate_id()` with shared `_make_id(prefix)` helper. Replaced duplicate `_make_command_id()` in `commands.py`.
- Centralized `utils/clock.py`: `utc_now_iso()` returning ISO 8601 string. Replaced inline `datetime.now(UTC).isoformat()` in `dispatcher.py`.
- CLI `run` validation: 9 rejection rules (fewer than 2 participants, missing moderator, no prompt source, multiple prompt sources, json+jsonl conflict, duplicate participants, non-positive max-rounds, nonexistent prompt file, invalid release-gate mode). `--release-gate` typed as `ReleaseGateMode` enum for compile-time and runtime validation.

### Phase 6: Happy-Path Consensus — Demo Checkpoint (2026-03-14)

22 new tests (6 happy-path + 5 event ordering + 4 run result + 3 human output + 2 JSON + 2 JSONL), 122 total.

- **Consensus orchestrator** (`consensus/orchestrator.py`): Full happy-path consensus loop — task framing → participant contributions → candidate synthesis → participant reviews → release gate → RunResult. Single-round only (approve/minor_revise); multi-round deferred to Phase 7.
- **Prompt templates** (`prompts/moderator.py`, `prompts/participant.py`): System+user message builders for all 5 consensus phases per PROMPT_SPEC. Shared contribution-labeling utility extracted to `prompts/labels.py`.
- **Output renderers** (`cli/render_human.py`, `cli/render_json.py`, `cli/render_jsonl.py`): Human mode (final answer on stdout, progress on stderr), JSON mode (single `model_dump_json()` object), JSONL mode (one event per line with monotonic sequence).
- **EventEmitter** used as central event factory for the orchestrator with batch-collect pattern.
- `duration_ms()` added to `utils/clock.py` for timestamp duration calculation.
- `_aggregate_usage()` sums tokens and cost_usd across all invocations.
- Dynamic consensus summary reflects actual vote distribution (approve/minor_revise counts).
- `schema_name` fields use `__name__` instead of hardcoded strings to stay in sync with model renames.
- Comprehensive inline comments on Phase 6 design constraints (single framing version, non-streaming, single-round).
