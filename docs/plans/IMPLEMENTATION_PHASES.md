# Nelson v1 Implementation Phases

## Document Status

- Status: Implementation plan ready for execution
- Scope: Nelson v1 CLI and headless orchestration core
- Repository state at time of writing: documentation-only, no implementation code exists
- Phase 0 (spec closeout from OPUS_PREPLAN): already complete — all contract decisions are resolved in normative documents

## 1. Understanding of the Documentation Structure

The Nelson repository contains twelve specification documents organized into three tiers.

### Normative contracts (implementation MUST conform to these)

| Document | Governs |
| --- | --- |
| `APPLICATION_PROTOCOL.md` | Command/event boundary, dispatcher shape, terminal results |
| `EVENT_SCHEMA.md` | Event envelope, all event types and payloads, ordering rules |
| `RUN_RESULT_SCHEMA.md` | `--json` output shape, success/partial/failure contracts |
| `CLI_SPEC.md` | Commands, flags, exit codes, output stream discipline |
| `PROMPT_SPEC.md` | Internal prompt schemas, structured output policy, repair |
| `ACCEPTANCE_TESTS.md` | Minimum test matrix and definition of done |
| `PYTHON_ENGINEERING_STANDARDS.md` | Typing, boundaries, async, error handling, observability |
| `PYPROJECT_TOOLING_SPEC.md` | Build system, toolchain, coverage, pre-commit |

### Supportive guidance (informs sequencing and implementation approach)

| Document | Purpose |
| --- | --- |
| `CODING_AGENT_HANDOFF.md` | Step-by-step execution guide with anti-patterns |
| `OPUS_PREPLAN.md` | Documentation review, recommended first visible slice |

### High-level context

| Document | Purpose |
| --- | --- |
| `PROJECT_CONTEXT.md` | Product identity, v1 scope, non-negotiable rules |
| `IMPLEMENTATION_PLAN.md` | Full product design, consensus strategy, milestones |

When tension exists between documents, the more specific normative contract wins. The handoff and pre-plan are treated as advice about ordering, not as overrides of contract details.

## 2. Implementation Strategy

### Sequencing logic

The plan sequences work around four principles:

1. **Types before behavior.** Every runtime module depends on the typed schemas — event envelope, command models, domain models, run result. These must exist and validate before orchestration code uses them.

2. **Auth before run.** Auth is the smallest complete user workflow through the full application protocol stack (command → dispatch → event → terminal result → CLI render). Building auth first proves the command/event boundary works end-to-end in real code.

3. **Happy path before hardening.** The first real `nelson run` should work end-to-end for the simplest successful case before adding multi-round logic, framing updates, repair, retry, quorum, and release gate edge cases.

4. **Contracts before renderers.** The three output modes (human, `--json`, `--jsonl`) are thin adapters over the event stream and `RunResult`. They should be built after the core produces valid events and results, not before.

### First visible user slice

The plan preserves the intended first demo checkpoint:

```bash
nelson auth set --api-key <KEY>
nelson auth status
nelson run \
  --participant openai/gpt-4.1-mini \
  --participant google/gemini-2.5-flash-lite:nitro \
  --moderator openai/gpt-4.1 \
  --prompt "Give me a concise comparison between FastAPI and Django for a new API project." \
  --json
```

This checkpoint arrives at the end of Phase 6. Everything before it is infrastructure that makes it possible; everything after it is hardening that makes it reliable.

### TDD discipline

Every phase follows the same cycle:

1. **Red:** Write tests first. Tests encode the phase's exit criteria as executable assertions. Tests MUST fail before implementation begins (confirming they test real behavior, not tautologies).
2. **Green:** Write the minimum implementation to make all tests pass.
3. **Refactor:** Clean up while keeping tests green. Run Ruff, Pyright, and the full test suite.

Tests are not an afterthought — they ARE the specification for each phase. The acceptance test IDs from `ACCEPTANCE_TESTS.md` are mapped to phases so it is clear which tests belong where.

### Session independence

Each phase is designed to be executed in a fresh session with cleared context. To support this:

- Every phase has a **Session start** section that tells the incoming agent what to read and how to verify the previous phase completed successfully.
- Progress is tracked in `docs/plans/PROGRESS.md`, updated at the end of each phase.
- The verification commands are runnable — the agent does not need to trust prior session claims.

## 3. Phased Plan

---

### Phase 1: Project Scaffold

#### Session start

**Read these docs:** `PYPROJECT_TOOLING_SPEC.md`, `PYTHON_ENGINEERING_STANDARDS.md`, `CLI_SPEC.md` (§1-2 only, for command surface)

**Verify previous phase:** This is the first phase. Verify the repo has no `src/` directory and no `pyproject.toml`:
```bash
test ! -d src && test ! -f pyproject.toml && echo "Ready to start Phase 1"
```

#### Objective

Make the repository runnable and testable. Establish the toolchain so every later phase inherits correct formatting, typing, and test infrastructure from the start.

#### TDD approach

This phase is an exception to strict TDD because there is no test infrastructure yet — the phase creates it. However, the CLI stub tests should still be written early in the phase and used to verify the Typer wiring.

**Tests to write:**

1. `tests/test_cli/test_help.py`:
   - `test_root_help` — `nelson --help` exits 0, output contains `auth` and `run`
   - `test_auth_help` — `nelson auth --help` exits 0
   - `test_run_help` — `nelson run --help` exits 0, output contains `--participant`, `--moderator`, `--json`, `--jsonl`

These tests map to acceptance tests **T-CLI-001** and **T-CLI-002**.

**Implementation to make them pass:**

- `pyproject.toml` — build system (hatchling), dependencies, tool config, console entrypoint
- `uv.lock` — locked dependency graph
- `.pre-commit-config.yaml`
- `src/nelson/__init__.py`
- `src/nelson/main.py` — Typer app root
- `src/nelson/cli/__init__.py`, `app.py`, `auth.py`, `run.py` — stubs with all flags declared
- `tests/__init__.py`, `tests/conftest.py`

#### Dependencies on earlier phases

None.

#### Out of scope

- Any real command logic (stubs only)
- Provider code, event models, consensus logic

#### Exit criteria

- All 3 CLI help tests pass
- `uv run ruff check .` passes
- `uv run ruff format --check .` passes
- `uv run pyright` passes
- Pre-commit hooks run successfully

#### Phase completion

Update `docs/plans/PROGRESS.md` with Phase 1 status and verification evidence.

---

### Phase 2: Typed Contracts

#### Session start

**Read these docs:** `APPLICATION_PROTOCOL.md`, `EVENT_SCHEMA.md`, `RUN_RESULT_SCHEMA.md`, `PROMPT_SPEC.md` (§3 for enums and typed shapes)

**Verify Phase 1 is complete:**
```bash
uv run nelson --help && uv run nelson auth --help && uv run nelson run --help && uv run pytest tests/test_cli/test_help.py -v && uv run pyright && echo "Phase 1 verified"
```

#### Objective

Define every Pydantic model, enum, and typed shape that the rest of the system depends on. Lock the system boundaries in code before runtime behavior expands.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_protocols/test_commands.py`:
   - `test_auth_set_command_validates` — construct `AuthSetCommand` with valid fields, assert it serializes to JSON
   - `test_auth_status_command_validates` — same for `AuthStatusCommand`
   - `test_auth_clear_command_validates` — same for `AuthClearCommand`
   - `test_run_command_validates` — construct `RunCommand` with all required fields, assert serialization
   - Maps to **T-PROTO-001**

2. `tests/test_protocols/test_events.py`:
   - `test_every_event_type_validates` — parametrize over all event types, construct one example of each, assert valid serialization
   - `test_event_schema_export` — export JSON Schema from the event discriminated union, assert it contains all event types
   - `test_command_received_example` — validate the canonical `command_received` payload from EVENT_SCHEMA.md §4.0
   - `test_run_started_example` — validate the canonical `run_started` payload from EVENT_SCHEMA.md §4.1
   - Maps to **T-EVENT-001** and **T-EVENT-004**

3. `tests/test_protocols/test_results.py`:
   - `test_run_result_success_example` — validate the canonical success JSON from RUN_RESULT_SCHEMA.md §12
   - `test_run_result_partial_example` — validate the canonical partial JSON from RUN_RESULT_SCHEMA.md §13
   - `test_run_result_failure_example` — validate the canonical failure JSON from RUN_RESULT_SCHEMA.md §14
   - `test_auth_set_result_validates` — validate AuthSetResult shape from APPLICATION_PROTOCOL.md §5.6
   - `test_auth_status_result_validates` — validate AuthStatusResult shape
   - `test_auth_clear_result_validates` — validate AuthClearResult shape

4. `tests/test_protocols/test_domain.py`:
   - `test_task_framing_result_validates` — validate shape from PROMPT_SPEC.md §4.3
   - `test_participant_contribution_validates` — validate shape from PROMPT_SPEC.md §5.3
   - `test_review_result_validates` — validate shape from PROMPT_SPEC.md §7.3
   - `test_release_gate_result_validates` — validate shape from PROMPT_SPEC.md §8.3
   - `test_usage_snapshot_validates` — validate shape from EVENT_SCHEMA.md §3.1

**Implementation to make them pass:**

- `src/nelson/protocols/__init__.py`
- `src/nelson/protocols/enums.py` — all enums
- `src/nelson/protocols/commands.py` — all command models
- `src/nelson/protocols/events.py` — event envelope + typed payloads + discriminated union
- `src/nelson/protocols/domain.py` — task framing, contribution, review, release gate, synthesis, usage, error, excluded participant
- `src/nelson/protocols/results.py` — RunResult, auth results
- `src/nelson/protocols/application.py` — CommandExecution protocol shape

#### Dependencies on earlier phases

Phase 1 (project exists, toolchain works).

#### Out of scope

- Runtime dispatching logic, provider code, prompt text, CLI argument validation beyond stubs

#### Exit criteria

- All protocol tests pass (command, event, result, domain round-trips)
- JSON Schema export works for the event discriminated union
- Pyright strict passes on all protocol modules

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 3: Auth and Credential Resolution

#### Session start

**Read these docs:** `CLI_SPEC.md` (§4-5), `APPLICATION_PROTOCOL.md` (§5.1-5.6), `ACCEPTANCE_TESTS.md` (§5)

**Verify Phase 2 is complete:**
```bash
uv run pytest tests/test_protocols/ -v && uv run pyright && echo "Phase 2 verified"
```

#### Objective

Deliver the first complete user workflow end-to-end through the full application protocol stack: CLI → typed command → dispatcher → core logic → event emission → terminal result → CLI rendering.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_auth/test_storage.py`:
   - `test_save_key_creates_directory_and_file(tmp_path)` — saves key, asserts file exists with correct content
   - `test_save_key_sets_restrictive_permissions(tmp_path)` — asserts file mode is 0o600
   - `test_save_key_overwrites_existing(tmp_path)` — saves twice, asserts second value
   - `test_read_key_returns_saved_value(tmp_path)` — save then read
   - `test_read_key_returns_none_when_absent(tmp_path)` — no file, returns None
   - `test_delete_key_removes_file(tmp_path)` — save, delete, assert gone
   - `test_delete_key_succeeds_when_absent(tmp_path)` — delete with no file, no error

2. `tests/test_auth/test_credentials.py`:
   - `test_cli_override_takes_precedence` — cli_key > env > saved
   - `test_env_var_takes_precedence_over_saved` — env > saved
   - `test_saved_key_used_as_fallback` — no cli, no env, uses saved
   - `test_no_key_available_raises` — no source returns error

3. `tests/test_auth/test_auth_cli.py`:
   - `test_auth_set_creates_key_file(tmp_home)` — exit 0, file created
   - `test_auth_set_missing_key_exits_2` — exit 2
   - `test_auth_status_no_key_exits_3(tmp_home)` — exit 3
   - `test_auth_status_with_saved_key_reports_present(tmp_home)` — output contains "present", "saved"
   - `test_auth_clear_removes_key(tmp_home)` — exit 0, file deleted
   - `test_auth_clear_succeeds_when_no_key(tmp_home)` — exit 0
   - `test_full_key_never_printed(tmp_home)` — set then status, assert full key not in stdout/stderr
   - Maps to **T-AUTH-001** through **T-AUTH-005**

4. `tests/test_auth/test_auth_protocol.py`:
   - `test_auth_set_emits_correct_events` — dispatch AuthSetCommand, assert event stream is `command_received → auth_key_saved → command_completed`
   - `test_auth_status_emits_correct_events` — same for AuthStatusCommand
   - `test_auth_clear_emits_correct_events` — same for AuthClearCommand
   - `test_auth_set_resolves_typed_result` — terminal result is `AuthSetResult`
   - Maps to **T-PROTO-003** (adapted for auth)

**Implementation to make them pass:**

- `src/nelson/storage/auth.py` — key read/write/delete, permission enforcement
- `src/nelson/core/dispatcher.py` — application protocol dispatcher for auth commands
- `src/nelson/core/credentials.py` — credential resolution order
- `src/nelson/cli/auth.py` — replace stubs with real logic

#### Dependencies on earlier phases

Phase 2 (command models, event models, auth result types exist).

#### Out of scope

- `RunCommand` dispatch, provider calls, OpenRouter verification call (may be stubbed)

#### Exit criteria

- All auth tests pass
- Auth commands flow through the dispatcher with correct event streams
- Terminal results are typed

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 4: Provider Abstraction and OpenRouter Adapter

#### Session start

**Read these docs:** `IMPLEMENTATION_PLAN.md` (§10.4, §7), `ACCEPTANCE_TESTS.md` (§2, §8), `PROMPT_SPEC.md` (§1.2)

**Verify Phase 3 is complete:**
```bash
uv run pytest tests/test_auth/ -v && uv run pytest tests/test_protocols/ -v && uv run pyright && echo "Phase 3 verified"
```

#### Objective

Make it possible to send prompts to real LLMs through OpenRouter. Establish the provider interface and the deterministic fake provider that the consensus engine and all future tests will depend on.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_providers/test_fake_provider.py`:
   - `test_fake_returns_structured_output` — configure fake with a valid response, invoke, assert parsed result matches
   - `test_fake_streams_deltas` — configure fake with delta sequence, stream, assert deltas arrive in order
   - `test_fake_simulates_timeout` — configure fake to timeout, invoke, assert `ProviderTimeoutError`
   - `test_fake_simulates_invalid_json` — configure fake to return bad JSON, invoke, assert `StructuredOutputInvalidError`
   - `test_fake_simulates_transport_failure` — configure fake to fail, invoke, assert `ProviderTransportError`
   - `test_fake_simulates_auth_failure` — configure fake to reject auth, invoke, assert `ProviderAuthError`
   - `test_fake_returns_usage` — configure fake with usage data, invoke, assert usage snapshot populated
   - Validates **ACCEPTANCE_TESTS.md §2** harness assumptions

2. `tests/test_providers/test_provider_interface.py`:
   - `test_provider_protocol_shape` — assert the interface defines `invoke` and `stream` with correct signatures
   - `test_fake_implements_provider_protocol` — assert FakeProvider satisfies the Protocol
   - `test_openrouter_implements_provider_protocol` — assert OpenRouterProvider satisfies the Protocol

3. `tests/test_providers/test_openrouter.py` (marked `live`):
   - `test_openrouter_non_streaming_call` — one real call, assert response has content
   - `test_openrouter_streaming_call` — one real streaming call, assert deltas arrive
   - `test_openrouter_extracts_usage` — assert usage snapshot from real call

4. `tests/test_core/test_errors.py`:
   - `test_domain_errors_exist` — assert all error types can be instantiated
   - `test_errors_map_to_error_codes` — each error type maps to CLI_SPEC.md §10 symbolic codes

**Implementation to make them pass:**

- `src/nelson/providers/base.py` — provider Protocol interface
- `src/nelson/providers/fake.py` — deterministic fake provider
- `src/nelson/providers/openrouter.py` — OpenRouter implementation (OpenAI SDK via `base_url` redirect, usage extraction, timeout)
- `src/nelson/core/errors.py` — domain exception types

#### Dependencies on earlier phases

Phase 2 (domain models for usage, errors), Phase 3 (credential resolution).

#### Out of scope

- Consensus orchestration, prompt construction, repair logic, event emission for model calls

#### Exit criteria

- All fake provider tests pass (7+ scenarios)
- Provider Protocol is satisfied by both FakeProvider and OpenRouterProvider
- Domain errors exist and map to error codes
- Optional: at least one live OpenRouter test passes

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 5: Event Stream Machinery and CLI `run` Validation

#### Session start

**Read these docs:** `EVENT_SCHEMA.md` (§1, §5), `CLI_SPEC.md` (§6.4)

**Verify Phase 4 is complete:**
```bash
uv run pytest tests/test_providers/ -v -m "not live" && uv run pytest tests/test_core/ -v && uv run pyright && echo "Phase 4 verified"
```

#### Objective

Build the runtime event emission infrastructure and complete CLI `run` argument validation. After this phase, the system can emit a properly ordered event stream and reject invalid `run` invocations.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_events/test_emitter.py`:
   - `test_sequence_starts_at_one` — emit one event, assert sequence == 1
   - `test_sequence_increases_monotonically` — emit 5 events, assert sequence is 1,2,3,4,5
   - `test_events_have_unique_ids` — emit 10 events, assert all event_ids are distinct
   - `test_event_ids_have_correct_prefix` — assert event_id starts with `evt_`
   - `test_timestamps_are_utc_iso8601` — assert timestamp format
   - `test_emitter_async_iteration` — iterate over emitter, collect events, assert order
   - Maps to **T-EVENT-002**

2. `tests/test_events/test_ids.py`:
   - `test_run_id_prefix` — `run_` prefix
   - `test_command_id_prefix` — `cmd_` prefix
   - `test_invocation_id_prefix` — `inv_` prefix
   - `test_candidate_id_prefix` — `cand_` prefix
   - `test_ids_are_unique` — generate 100, assert no duplicates

3. `tests/test_cli/test_run_validation.py`:
   - `test_fewer_than_two_participants_exits_2` — exit 2
   - `test_missing_moderator_exits_2` — exit 2
   - `test_no_prompt_source_exits_2` — exit 2
   - `test_multiple_prompt_sources_exits_2` — exit 2
   - `test_json_and_jsonl_together_exits_2` — exit 2
   - `test_duplicate_participants_exits_2` — exit 2
   - `test_max_rounds_non_positive_exits_2` — exit 2
   - Maps to **T-CLI-003** through **T-CLI-007**

**Implementation to make them pass:**

- `src/nelson/core/events.py` — EventEmitter class
- `src/nelson/utils/ids.py` — ID generation
- `src/nelson/utils/clock.py` — UTC timestamp helper
- `src/nelson/cli/run.py` — full argument validation

#### Dependencies on earlier phases

Phase 2 (event models, enums), Phase 1 (CLI stub).

#### Out of scope

- Rendering the event stream to stdout, consensus logic, provider calls from the event emitter

#### Exit criteria

- All emitter tests pass (monotonic sequence, unique IDs, async iteration)
- All CLI validation tests pass (7+ rejection cases)

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 6: Happy-Path Consensus and First Visible Run

#### Session start

**Read these docs:** `PROMPT_SPEC.md`, `IMPLEMENTATION_PLAN.md` (§6.1-6.9), `RUN_RESULT_SCHEMA.md`, `CLI_SPEC.md` (§7-9), `APPLICATION_PROTOCOL.md` (§10)

**Verify Phases 3-5 are complete:**
```bash
uv run pytest -v -m "not live" && uv run pyright && echo "Phases 1-5 verified"
```

#### Objective

Deliver the first genuinely useful end-to-end `nelson run`. This is the first demo checkpoint. The consensus engine handles only the simplest successful path: one framing round, one contribution round, one synthesis, one review round where everyone approves (or only `minor_revise`), optional release gate, final answer.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_consensus/test_happy_path.py`:
   - `test_happy_path_success` — fake provider configured for approval, run consensus, assert `status = "success"`, `final_answer` is not None, `rounds_completed` is 1
   - `test_task_framing_produces_valid_result` — assert framing returns valid `TaskFramingResult`
   - `test_participants_produce_valid_contributions` — assert each participant returns valid `ParticipantContribution`
   - `test_moderator_produces_valid_synthesis` — assert moderator returns valid `CandidateSynthesisResult`
   - `test_participants_produce_valid_reviews` — assert reviews are valid `ReviewResult` with decision `approve`
   - `test_release_gate_executes_in_auto_mode` — assert release gate runs and produces `pass` or `pass_with_minor_fixes`
   - Maps to **T-CONS-001**

2. `tests/test_consensus/test_event_stream_ordering.py`:
   - `test_event_stream_starts_with_command_received` — first event type is `command_received`
   - `test_run_started_follows_command_received` — `run_started` comes after `command_received`
   - `test_run_completed_before_command_completed` — `run_completed` before `command_completed`
   - `test_task_framing_events_before_contributions` — `task_framing_completed` before `model_started` for participants
   - `test_no_model_delta_for_structured_internal_phases` — structured phases emit no `model_delta`
   - Maps to **T-PROTO-002**, **T-EVENT-005**

3. `tests/test_consensus/test_run_result.py`:
   - `test_run_result_has_all_required_fields` — assert all top-level fields from RUN_RESULT_SCHEMA.md are present
   - `test_run_result_validates_against_schema` — full RunResult matches Pydantic model
   - `test_run_result_timing_is_populated` — started_at, completed_at, duration_ms are present
   - `test_run_result_usage_is_populated` — per_invocation list and total are present

4. `tests/test_output/test_json_output.py`:
   - `test_json_mode_outputs_single_json_object` — stdout is exactly one JSON document
   - `test_json_mode_no_progress_on_stdout` — no non-JSON text on stdout
   - Maps to **T-OUT-002**

5. `tests/test_output/test_jsonl_output.py`:
   - `test_jsonl_mode_outputs_json_lines` — every stdout line parses as JSON
   - `test_jsonl_events_have_monotonic_sequence` — sequence is 1,2,3,...
   - Maps to **T-OUT-003**

6. `tests/test_output/test_human_output.py`:
   - `test_human_mode_final_answer_on_stdout` — stdout contains the final answer text
   - `test_human_mode_progress_on_stderr` — stderr contains progress text
   - `test_human_mode_consensus_status_shown` — output contains consensus status
   - Maps to **T-OUT-001**

**Implementation to make them pass:**

- `src/nelson/prompts/participant.py` — system prompt, contribution prompt, review prompt
- `src/nelson/prompts/moderator.py` — system prompt, task framing, synthesis, release gate prompts
- `src/nelson/prompts/repair.py` — repair prompt template
- `src/nelson/consensus/orchestrator.py` — main consensus loop (happy path)
- `src/nelson/consensus/task_framing.py`, `synthesis.py`, `review.py`, `release_gate.py`, `stopping.py`
- `src/nelson/core/engine.py` — RunCommand execution
- `src/nelson/core/dispatcher.py` — extend for RunCommand
- `src/nelson/core/session.py` — run session state
- `src/nelson/cli/render_human.py`, `render_json.py`, `render_jsonl.py`

#### Dependencies on earlier phases

Phase 2 (all typed contracts), Phase 3 (credential resolution, dispatcher), Phase 4 (provider + fake provider), Phase 5 (event emitter, CLI validation).

#### Out of scope

- Multi-round continuation after `major_revise` or `reject`
- Framing updates / `task_framing_updated` event
- Participant exclusion, retry, repair, quorum loss, moderator failure
- Release gate `fail` path
- Progress weighting accuracy (placeholder estimates OK)

#### Exit criteria

- All consensus happy-path tests pass
- All event stream ordering tests pass
- All output mode tests pass
- One live OpenRouter smoke run succeeds (T-LIVE-001)

#### Phase completion

Update `docs/plans/PROGRESS.md`. **This is the first demo checkpoint.**

---

### Phase 7: Multi-Round Consensus and Framing Updates

#### Session start

**Read these docs:** `IMPLEMENTATION_PLAN.md` (§6.6-6.10, §6.3 reframing rules), `EVENT_SCHEMA.md` (§4.9b, §4.14-4.17, §5 ordering rules), `ACCEPTANCE_TESTS.md` (§7)

**Verify Phase 6 is complete:**
```bash
uv run pytest -v -m "not live" && uv run pyright && echo "Phase 6 verified"
```
Additionally, verify the happy-path demo works:
```bash
uv run pytest tests/test_consensus/test_happy_path.py -v && echo "Happy path confirmed"
```

#### Objective

Extend the consensus engine from happy-path-only to spec-complete multi-round behavior, including blocking reviews, continuation rounds, early stop, max-round exhaustion, and material framing updates.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_consensus/test_multi_round.py`:
   - `test_major_revise_triggers_new_round` — fake provider returns `major_revise` in round 1, `approve` in round 2, assert 2 rounds completed
   - `test_reject_triggers_new_round` — same with `reject`
   - `test_minor_revise_does_not_block_closure` — all `minor_revise`, assert consensus reached in 1 round
   - `test_minor_revise_feedback_incorporated` — assert `minor_revisions_applied` in result
   - `test_early_stop_before_max_rounds` — `max_rounds=10`, consensus in round 2, assert `rounds_completed=2`
   - Maps to **T-CONS-002**, **T-CONS-003**

2. `tests/test_consensus/test_partial_consensus.py`:
   - `test_max_rounds_exhausted_returns_partial` — persistent `major_revise`, `max_rounds=2`, assert `status = "partial"`, `final_answer` not None
   - `test_residual_disagreements_populated` — assert `residual_disagreements` list is non-empty
   - `test_human_output_shows_partial_consensus` — human output contains "partial" and disagreement info
   - Maps to **T-CONS-004**, **T-OUT-004**

3. `tests/test_consensus/test_framing_update.py`:
   - `test_material_framing_update_emits_event` — participant raises `major_issue`, moderator updates framing, assert `task_framing_updated` event emitted
   - `test_invalidated_candidate_no_review_events` — assert no `review_started`, `review_completed`, or `consensus_*` events for invalidated candidate
   - `test_reframed_contribution_used_after_update` — assert participants use `reframed_contribution` purpose, not `initial_contribution`
   - `test_framing_version_increments` — assert framing_version goes from 1 to 2
   - `test_invalidated_round_counts_toward_budget` — assert `rounds_completed` includes the invalidated round
   - Maps to **T-CONS-005**

4. `tests/test_consensus/test_framing_budget.py`:
   - `test_framing_update_no_budget_fails` — framing update in last round, assert run fails with `framing_update_budget_exhausted`
   - Maps to **T-CONS-006**

5. `tests/test_consensus/test_anonymized_review.py`:
   - `test_review_context_uses_labels_not_model_ids` — assert participant review inputs contain `response_a`, `response_b` labels, not real model identifiers

**Implementation to make them pass:**

- Extend `consensus/orchestrator.py` — multi-round loop, candidate update cycle
- Extend `consensus/review.py` — blocking rule enforcement
- Extend `consensus/synthesis.py` — re-synthesis with review feedback, anonymized excerpts
- Extend `consensus/task_framing.py` — `task_framing_updated`, framing version tracking, candidate invalidation
- Extend `core/session.py` — framing version management, invalidated candidate tracking

#### Dependencies on earlier phases

Phase 6 (happy-path consensus works).

#### Out of scope

- Retry and repair for invalid structured output (Phase 8)
- Participant exclusion (Phase 8)
- Quorum loss (Phase 8)
- Moderator failure (Phase 8)

#### Exit criteria

- All multi-round tests pass
- All partial consensus tests pass
- All framing update tests pass (including budget exhaustion)
- Anonymized review context test passes

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 8: Retry, Repair, Failure Policies, and Participant Exclusion

#### Session start

**Read these docs:** `IMPLEMENTATION_PLAN.md` (§7), `EVENT_SCHEMA.md` (§4.13, §4.13b), `CLI_SPEC.md` (§3, §10), `ACCEPTANCE_TESTS.md` (§8), `PROMPT_SPEC.md` (§9)

**Verify Phase 7 is complete:**
```bash
uv run pytest tests/test_consensus/ -v && uv run pyright && echo "Phase 7 verified"
```

#### Objective

Implement the resilience layer: structured output repair, provider retry, participant exclusion, quorum enforcement, moderator failure, and timeout enforcement at the consensus level.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_failure/test_repair.py`:
   - `test_invalid_json_triggers_repair` — fake provider returns invalid JSON, repair succeeds, assert run completes
   - `test_repaired_output_is_used_downstream` — assert the repaired structured output is used in consensus
   - Maps to **T-FAIL-001**

2. `tests/test_failure/test_participant_exclusion.py`:
   - `test_failed_repair_excludes_participant` — repair fails, assert `participant_excluded` event emitted immediately after failure chain
   - `test_excluded_participant_permanently_removed` — assert excluded participant does not participate in later rounds
   - `test_run_continues_with_quorum` — 3 participants, 1 excluded, assert run continues with 2
   - Maps to **T-FAIL-002**

3. `tests/test_failure/test_quorum.py`:
   - `test_quorum_loss_fails_run` — 2 of 3 participants fail, assert run fails with `participant_quorum_lost`
   - `test_quorum_loss_exit_code_6` — assert exit code 6
   - `test_quorum_loss_no_round_completed` — assert `round_completed` is NOT emitted for the interrupted round
   - Maps to **T-FAIL-003**

4. `tests/test_failure/test_moderator_failure.py`:
   - `test_moderator_retry_succeeds` — moderator fails once, retry succeeds, assert run completes
   - `test_moderator_retry_fails_aborts_run` — moderator fails twice, assert run fails with `moderator_failed`
   - `test_moderator_failure_exit_code_6` — assert exit code 6
   - Maps to **T-FAIL-004**, **T-FAIL-005**

5. `tests/test_failure/test_timeout.py`:
   - `test_provider_timeout_enforced` — fake provider hangs, assert timeout error emitted
   - Maps to **T-FAIL-006**

6. `tests/test_failure/test_exclusion_during_review.py`:
   - `test_exclusion_during_review_round_can_close` — one participant excluded during review, remaining reviewers allow closure
   - `test_review_completed_reflects_actual_reviewers` — `reviewer_count` matches remaining participants
   - Maps to **T-FAIL-007**

7. `tests/test_failure/test_usage_accounting.py`:
   - `test_usage_includes_failed_calls` — usage.total includes tokens from failed invocations
   - `test_usage_includes_repair_calls` — usage.total includes repair invocation tokens
   - `test_usage_incomplete_when_missing` — `is_complete = false` when any invocation lacks usage

**Implementation to make them pass:**

- `src/nelson/consensus/repair.py` — one repair attempt using repair prompt
- `src/nelson/consensus/retry.py` — one network retry
- Extend `consensus/orchestrator.py` — participant exclusion, quorum checks, moderator failure abort
- Extend `core/session.py` — excluded participant tracking
- Extend `core/errors.py` — quorum-loss, structured-output-repair-failed errors

#### Dependencies on earlier phases

Phase 7 (multi-round consensus works).

#### Out of scope

- Logfire instrumentation (Phase 9)
- README (Phase 10)

#### Exit criteria

- All failure and repair tests pass (T-FAIL-001 through T-FAIL-007)
- Exit codes match CLI_SPEC.md
- Usage accounting is correct for all paths

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 9: Observability and Progress Polish

#### Session start

**Read these docs:** `PYTHON_ENGINEERING_STANDARDS.md` (§7), `IMPLEMENTATION_PLAN.md` (§12), `EVENT_SCHEMA.md` (§4.4)

**Verify Phase 8 is complete:**
```bash
uv run pytest -v -m "not live" && uv run pyright && echo "Phase 8 verified"
```

#### Objective

Add optional Logfire instrumentation and refine the progress indicator to match the documented weighting model.

#### TDD approach

**Tests to write FIRST:**

1. `tests/test_progress/test_progress_calculation.py`:
   - `test_startup_phase_weight_is_5_percent` — assert startup phase contributes ~5% to overall estimate
   - `test_framing_phase_weight_is_10_percent` — assert framing contributes ~10%
   - `test_progress_events_have_required_fields` — assert `phase_name`, `phase_index`, `phase_count_estimate`, `stage_progress`, `overall_progress_estimate`, `is_estimate` are present
   - `test_overall_progress_marked_as_estimate` — assert `is_estimate = true`
   - `test_early_stop_progress_jumps` — consensus at round 2 of 10, progress jumps to near completion

2. `tests/test_observability/test_logfire_disabled.py`:
   - `test_runs_correctly_without_logfire_config` — full run with Logfire not configured, assert no errors
   - `test_no_logfire_import_errors` — import the logfire setup module, assert no failure when Logfire unconfigured

**Implementation to make them pass:**

- `src/nelson/core/progress.py` — progress weight model
- Refine `src/nelson/cli/render_human.py` — compact progress format
- `src/nelson/utils/logfire.py` — optional Logfire setup, HTTPX/Pydantic instrumentation, manual spans

#### Dependencies on earlier phases

Phase 8 (all consensus and failure paths work).

#### Out of scope

- New features, README

#### Exit criteria

- Progress events have meaningful estimates
- Human mode shows compact progress
- All existing tests still pass
- Code runs without Logfire configured

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

### Phase 10: Validation, Documentation, and Release Readiness

#### Session start

**Read these docs:** `ACCEPTANCE_TESTS.md` (entire document), `PROJECT_CONTEXT.md`

**Verify Phase 9 is complete:**
```bash
uv run pytest -v -m "not live" && uv run pyright && uv run ruff check . && echo "Phase 9 verified"
```

#### Objective

Run the full acceptance test matrix, add a root README, and confirm the implementation matches every normative document.

#### TDD approach

This phase is primarily a gap-filling and verification phase. The approach is:

1. Run the full test suite and identify any acceptance tests from ACCEPTANCE_TESTS.md that are not yet covered.
2. Write missing tests.
3. Fix any failures.
4. Run coverage and fill gaps to meet thresholds.

**Specific checks:**

- All T-CLI tests (001-007) ✓
- All T-AUTH tests (001-005) ✓
- All T-PROTO tests (001-004) ✓
- All T-EVENT tests (001-005) ✓
- All T-CONS tests (001-006) ✓
- All T-FAIL tests (001-007) ✓
- All T-OUT tests (001-004) ✓
- At least one T-LIVE test (001 or 002) ✓
- Coverage: 90% line, 85% branch

**Implementation:**

- `README.md` — project purpose, setup, bootstrap commands, auth example, run example
- Any missing test coverage

#### Dependencies on earlier phases

All previous phases.

#### Out of scope

- Any feature work beyond v1

#### Exit criteria

- Full acceptance test matrix passes
- Coverage meets thresholds
- All toolchain checks pass
- README exists with quickstart
- At least one live smoke test passes

#### Phase completion

Update `docs/plans/PROGRESS.md` with final status.

---

### Phase 11: Structured Logging and Observability

#### Session start

**Read these docs:** `PYTHON_ENGINEERING_STANDARDS.md` (§7 Observability), `EVENT_SCHEMA.md`

**Verify Phase 10 is complete:**
```bash
uv run pytest -v -m "not live" && uv run pyright && uv run ruff check . && echo "Phase 10 verified"
```

#### Objective

Add structured logging throughout the entire codebase so that every significant decision, state transition, and failure is observable in production. Nelson should be fully debuggable from its logs alone — without a debugger, without reproducing the issue.

#### TDD approach

**Tests to write FIRST (all must fail initially):**

1. `tests/test_observability/test_logging.py`:
   - `test_provider_invoke_logs_request_and_response` — assert structured log entries are emitted for every provider call (model, message count, finish reason, token usage)
   - `test_provider_invoke_logs_on_failure` — assert error details are logged with full context when a provider call fails
   - `test_provider_stream_logs_lifecycle` — assert log entries for stream open, delta count, usage, and close
   - `test_consensus_round_logs_decisions` — assert each consensus round logs participant count, review decisions, and outcome
   - `test_structured_output_parse_failure_logged` — assert a warning is logged when JSON parsing fails in the provider layer (the silent `contextlib.suppress` path)
   - `test_credential_resolution_logs_source` — assert which credential source was used (CLI override, env var, saved key) is logged
   - `test_log_entries_are_structured_json` — assert log output is machine-parseable structured JSON, not free-form text

**Implementation:**

- `src/nelson/core/logging.py` — logging configuration, structured formatter, context injection (run ID, phase, model)
- Add `structlog` or `logfire` as the logging backend (per PYTHON_ENGINEERING_STANDARDS.md §7)
- Instrument every module with structured log calls at appropriate levels:
  - **DEBUG**: request/response payloads, SSE frame parsing, credential resolution steps
  - **INFO**: provider calls (model, token count, latency), consensus round outcomes, phase transitions
  - **WARNING**: silent fallbacks (JSON parse failure, unknown finish_reason, missing usage data), retry attempts
  - **ERROR**: provider failures, quorum loss, structured output repair failures
- Add correlation context: run ID, round number, participant model, invocation purpose
- Ensure no sensitive data is logged (API keys, full prompts in production mode)

#### Dependencies on earlier phases

All previous phases (everything must work before adding observability).

#### Out of scope

- External log aggregation setup (Datadog, CloudWatch, etc.)
- Log rotation or retention policies
- Performance profiling or tracing spans (beyond what logfire provides out of the box)

#### Exit criteria

- Every provider call (invoke and stream) emits structured log entries
- Every consensus decision point is logged with context
- Every silent fallback or suppressed error emits a warning-level log
- All log entries are structured JSON with consistent field names
- No API keys or full prompt content appear in logs
- All existing tests still pass (logging must not change behavior)
- At least one integration test verifies end-to-end log output for a full consensus run

#### Phase completion

Update `docs/plans/PROGRESS.md`.

---

## 4. Parallelization Guidance

### What can be developed in parallel

Within each phase, some work is internally parallelizable:

- **Phase 2:** Command models, event models, domain models, and result models are independent of each other. They can be written in parallel as long as shared enums are defined first.
- **Phase 4:** The OpenRouter adapter and the fake provider are independent implementations of the same interface. They can be built in parallel once the provider Protocol is defined.
- **Phase 6:** Prompt modules (participant, moderator, repair) are independent of each other. CLI renderers (human, JSON, JSONL) are independent of each other.

### What must remain sequential

The phase sequence itself is strictly sequential:

| Phase | Hard dependency |
| --- | --- |
| Phase 2 | Phase 1 (project exists) |
| Phase 3 | Phase 2 (command/event models exist) |
| Phase 4 | Phase 2 (domain models), Phase 3 (credentials) |
| Phase 5 | Phase 2 (event models) |
| Phase 6 | Phase 3 + 4 + 5 (all infrastructure in place) |
| Phase 7 | Phase 6 (happy-path consensus works) |
| Phase 8 | Phase 7 (multi-round consensus works) |
| Phase 9 | Phase 8 (all failure paths work) |
| Phase 10 | Phase 9 (everything works) |
| Phase 11 | Phase 10 (full acceptance suite passes) |

**Note:** Phases 4 and 5 depend on Phase 2 but not on each other. They could theoretically be developed in parallel, but sequential execution within a single session is simpler.

### Anti-parallelization warnings

- Do NOT build consensus logic (Phase 6+) before typed contracts (Phase 2) are stable.
- Do NOT build CLI renderers before the event emitter (Phase 5) and happy-path consensus (Phase 6) are working.
- Do NOT build failure/repair logic (Phase 8) before multi-round consensus (Phase 7) is stable.

## 5. Risk Checkpoints

### Checkpoint 1: After Phase 2 — Schema alignment

**Risk:** Pydantic models diverge from documented JSON examples.

**Verification:** Run every canonical example from EVENT_SCHEMA.md and RUN_RESULT_SCHEMA.md through `model_validate`. If any example fails, fix the model before proceeding.

### Checkpoint 2: After Phase 3 — Application protocol proof

**Risk:** The dispatcher/event-stream/terminal-result architecture is too awkward in practice.

**Verification:** Confirm auth commands go through `dispatch → CommandExecution → events + result`. If the protocol shape does not work cleanly for auth, it will not work for `run` either.

### Checkpoint 3: After Phase 4 — Provider contract stability

**Risk:** Provider interface is wrong for what the consensus engine needs.

**Verification:** Confirm the fake provider can simulate all modes from ACCEPTANCE_TESTS.md §2. Confirm at least one real OpenRouter call works. Adjust the provider interface here, not in Phase 6.

### Checkpoint 4: After Phase 6 — First visible run

**Risk:** Event stream is subtly wrong (ordering, missing fields, wrong phase/role values).

**Verification:** Run the happy-path test in `--jsonl` mode and validate every event against the schema. Manually inspect `--json` output against RUN_RESULT_SCHEMA.md §12. This is the most important checkpoint.

### Checkpoint 5: After Phase 7 — Consensus edge cases

**Risk:** Framing update semantics are wrong (e.g., review events emitted for invalidated candidates).

**Verification:** Run T-CONS-005 and T-CONS-006. Trace emitted events line by line against EVENT_SCHEMA.md §5 ordering rules.

### Checkpoint 6: After Phase 8 — Failure semantics

**Risk:** Participant exclusion and quorum loss interact subtly with round accounting.

**Verification:** Run T-FAIL-002, T-FAIL-003, T-FAIL-007. Verify `round_completed` is emitted or suppressed correctly in each case.

## 6. First Implementation Session

### Recommendation

The best first working session covers **Phase 1 and Phase 2 together**.

### Rationale

- Phase 1 alone produces only a skeleton — useful but not meaningful progress.
- Phase 2 depends only on Phase 1 and is pure modeling work with no runtime complexity.
- Both together mean the agent finishes with: a fully tooled project, every typed contract defined and validated, JSON Schema export working, and all canonical doc examples passing through Pydantic.

### TDD flow for the first session

1. Create `pyproject.toml`, package skeleton, and test infrastructure (Phase 1 scaffold)
2. Write CLI help tests → make them pass with Typer stubs
3. Write all protocol tests (commands, events, domain, results) → they all fail (Red)
4. Implement enums → implement models → tests go green one by one (Green)
5. Run Ruff, Pyright, full suite (Refactor)

### Expected end state

After the first session:
- `uv run pytest` passes with all schema validation and CLI help tests
- All toolchain commands pass
- The typed contract layer is complete and verified against documented examples
- `docs/plans/PROGRESS.md` shows Phase 1 and Phase 2 as complete
