# Nelson v1 Acceptance Test Plan

## Purpose

This document defines the minimum acceptance tests Claude should use while implementing Nelson v1.

The goal is to remove ambiguity about what "done" means for each subsystem.

## Normative References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)

## 1. Test Strategy

Nelson v1 should be tested at three levels:

1. pure schema and validation tests
2. mock-provider orchestration tests
3. optional live OpenRouter smoke tests

Most acceptance tests should use a deterministic mock provider. Live API smoke tests should be few and isolated.

## 2. Test Harness Assumptions

The implementation should provide or make easy a fake provider that can:

- return deterministic structured outputs
- stream deterministic deltas
- simulate timeout
- simulate invalid JSON
- simulate transport failure
- simulate participant dropout
- simulate moderator failure

This is required to validate consensus and repair behavior without paying for real calls.

## 3. Acceptance Test Matrix

Each test below includes:

- ID
- level
- setup
- action
- expected result

## 4. CLI Validation Tests

### T-CLI-001

- Level: unit/integration
- Setup: no credentials needed
- Action: run `uv run nelson --help`
- Expected result:
  - exit code `0`
  - help output contains `auth`
  - help output contains `run`

### T-CLI-002

- Level: unit/integration
- Setup: no credentials needed
- Action: run `uv run nelson run --help`
- Expected result:
  - exit code `0`
  - help output mentions repeatable `--participant`
  - help output mentions `--moderator`
  - help output mentions `--json` and `--jsonl`

### T-CLI-003

- Level: integration
- Setup: no credentials needed
- Action: run `uv run nelson run --moderator openai/gpt-4.1 --prompt "test"`
- Expected result:
  - exit code `2`
  - error indicates at least two participants are required

### T-CLI-004

- Level: integration
- Setup: no credentials needed
- Action: run `uv run nelson run --participant openai/gpt-4.1 --participant anthropic/claude-3.7-sonnet --prompt "test"`
- Expected result:
  - exit code `2`
  - error indicates moderator is required

### T-CLI-005

- Level: integration
- Setup: no credentials needed
- Action: run `uv run nelson run --participant openai/gpt-4.1 --participant anthropic/claude-3.7-sonnet --moderator openai/gpt-4.1 --prompt "x" --stdin`
- Expected result:
  - exit code `2`
  - error indicates only one input source is allowed

### T-CLI-006

- Level: integration
- Setup: no credentials needed
- Action: run `uv run nelson run --participant openai/gpt-4.1 --participant anthropic/claude-3.7-sonnet --moderator openai/gpt-4.1 --prompt "x" --json --jsonl`
- Expected result:
  - exit code `2`
  - error indicates output modes are mutually exclusive

### T-CLI-007

- Level: integration
- Setup: no credentials needed
- Action: run `uv run nelson run --participant openai/gpt-4.1 --participant openai/gpt-4.1 --moderator openai/gpt-4.1 --prompt "x"`
- Expected result:
  - exit code `2`
  - error indicates duplicate participant models are not allowed

## 5. Auth Tests

### T-AUTH-001

- Level: integration
- Setup: isolate `HOME` to a temporary directory
- Action: run `uv run nelson auth set --api-key sk-test`
- Expected result:
  - exit code `0`
  - `~/.nelson/openrouter_api_key` is created
  - file contents equal `sk-test`

### T-AUTH-002

- Level: integration
- Setup: temporary `HOME`, no key saved, no env var
- Action: run `uv run nelson auth status`
- Expected result:
  - exit code `3`
  - output reports no effective key

### T-AUTH-003

- Level: integration/live optional
- Setup: set `OPENROUTER_API_KEY` to a valid key
- Action: run `uv run nelson auth status`
- Expected result:
  - exit code `0`
  - output reports effective source `env`
  - verification succeeds

### T-AUTH-004

- Level: integration/live optional
- Setup: set `OPENROUTER_API_KEY` to an invalid key
- Action: run `uv run nelson auth status`
- Expected result:
  - exit code `4`
  - output reports verification failed

### T-AUTH-005

- Level: integration
- Setup: temporary `HOME`, saved key present
- Action: run `uv run nelson auth clear`
- Expected result:
  - exit code `0`
  - saved key file is deleted

## 6. Event Protocol Tests

### T-PROTO-001

- Level: unit
- Setup: instantiate all application command models
- Action: validate and serialize `AuthSetCommand`, `AuthStatusCommand`, `AuthClearCommand`, and `RunCommand`
- Expected result:
  - every command validates
  - command serialization is JSON-compatible

### T-PROTO-002

- Level: integration with mock application service
- Setup: dispatch a `RunCommand`
- Action: capture the full event stream and await the terminal execution result
- Expected result:
  - the first event is `command_received`
  - `run_started` occurs after `command_received`
  - terminal application event is `command_completed` or `command_failed`
  - the terminal execution result resolves to a typed `RunResult`

### T-PROTO-003

- Level: integration with mock application service
- Setup: dispatch `AuthStatusCommand`
- Action: capture the full event stream and await the terminal execution result
- Expected result:
  - the stream includes `command_received`
  - the stream includes `auth_status_reported`
  - the stream terminates with `command_completed` or `command_failed`
  - the terminal execution result resolves to a typed `AuthStatusResult`

### T-PROTO-004

- Level: integration with mock application service
- Setup: dispatch a `RunCommand` that fails after runtime startup
- Action: capture the full event stream and await the terminal execution result
- Expected result:
  - the stream includes `run_failed`
  - the stream terminates with `command_failed`
  - the terminal execution result resolves to a typed `RunResult` with `status = "failed"`

### T-EVENT-001

- Level: unit
- Setup: instantiate all event models
- Action: serialize one example of each event type
- Expected result:
  - every event validates
  - serialization produces JSON-compatible output

### T-EVENT-002

- Level: unit
- Setup: mock run with multiple participants and streaming
- Action: capture emitted events
- Expected result:
  - `sequence` starts at `1`
  - `sequence` increases monotonically without gaps
  - terminal event is `run_completed` or `run_failed`

### T-EVENT-003

- Level: integration
- Setup: mock provider emits provider keepalive/comment frames during a text-bearing streaming invocation
- Action: run the invocation
- Expected result:
  - no keepalive frame is surfaced as `model_delta`
  - only content-bearing deltas appear in stdout JSONL

### T-EVENT-004

- Level: unit
- Setup: schema export
- Action: export JSON Schema for event models
- Expected result:
  - schema export succeeds
  - discriminated event union is represented

### T-EVENT-005

- Level: integration with mock provider
- Setup: one structured internal invocation succeeds
- Action: capture emitted events
- Expected result:
  - `model_started` is emitted
  - `model_completed` is emitted
  - no `model_delta` event is emitted for that structured internal phase

## 7. Consensus Flow Tests

### T-CONS-001

- Level: integration with mock provider
- Setup: two participants and one moderator, all successful
- Action: run a one-round consensus that converges immediately
- Expected result:
  - task framing occurs first
  - participant initial contributions occur
  - candidate is created
  - reviews are submitted
  - consensus reaches `reached`
  - final result status is `success`

### T-CONS-002

- Level: integration with mock provider
- Setup: first candidate receives one `major_revise`, second candidate is approved
- Action: run with `max_rounds=10`
- Expected result:
  - at least two rounds execute
  - first round emits `consensus_pending`
  - second round emits `consensus_reached`

### T-CONS-003

- Level: integration with mock provider
- Setup: only `minor_revise` remains after review
- Action: run consensus
- Expected result:
  - consensus can close without another blocking round
  - final result status is `success`
  - applied minor revisions are visible in result metadata

### T-CONS-004

- Level: integration with mock provider
- Setup: blocking disagreements persist until round budget is exhausted
- Action: run with `max_rounds=2`
- Expected result:
  - final status is `partial`
  - final answer is not null
  - residual disagreements are present

### T-CONS-005

- Level: integration with mock provider
- Setup: participant objects challenge task framing substantially in round 1
- Action: run consensus
- Expected result:
  - moderator emits `task_framing_updated`
  - the invalidated candidate receives no `review_*` events
  - the invalidated candidate receives no `consensus_*` events
  - later round uses the updated framing version
  - later round uses `reframed_contribution` for fresh participant contributions

### T-CONS-006

- Level: integration with mock provider
- Setup: the moderator identifies a material framing update in the last available round
- Action: run consensus with no remaining round budget after that update
- Expected result:
  - `task_framing_updated` is emitted
  - the run fails
  - the error code is `framing_update_budget_exhausted`

## 8. Failure and Repair Tests

### T-FAIL-001

- Level: integration with mock provider
- Setup: one participant returns invalid JSON but repair succeeds
- Action: run consensus
- Expected result:
  - one repair attempt occurs
  - run succeeds
  - repaired structured output is used downstream

### T-FAIL-002

- Level: integration with mock provider
- Setup: one participant returns invalid JSON and repair fails
- Action: run consensus with three participants total
- Expected result:
  - `participant_excluded` is emitted immediately after the failure chain completes
  - failed participant is dropped
  - run continues because quorum remains at two

### T-FAIL-003

- Level: integration with mock provider
- Setup: two participants fail irrecoverably, leaving one valid participant
- Action: run consensus
- Expected result:
  - run fails
  - exit code is `6`
  - error code is `participant_quorum_lost`

### T-FAIL-004

- Level: integration with mock provider
- Setup: moderator fails once, retry succeeds
- Action: run consensus
- Expected result:
  - run completes
  - retry count is visible in emitted events where relevant

### T-FAIL-005

- Level: integration with mock provider
- Setup: moderator fails twice
- Action: run consensus
- Expected result:
  - run fails
  - exit code is `6`
  - error code is `moderator_failed`

### T-FAIL-006

- Level: integration with mock provider
- Setup: provider call hangs beyond 60 seconds
- Action: run consensus
- Expected result:
  - timeout is enforced
  - provider timeout error is emitted

### T-FAIL-007

- Level: integration with mock provider
- Setup: one participant is excluded during candidate review, but at least two active participants remain
- Action: run consensus
- Expected result:
  - `review_started` target count reflects the active set at review start
  - `participant_excluded` is emitted during the review phase
  - `review_completed.reviewer_count` reflects only the valid remaining reviewers
  - consensus may still close in the same round if no blocking issues remain

## 9. Output Mode Tests

### T-OUT-001

- Level: integration with mock provider
- Setup: successful run in human mode
- Action: execute `nelson run ...`
- Expected result:
  - progress lines appear on `stderr`
  - final answer appears on `stdout`
  - consensus status appears in final output

### T-OUT-002

- Level: integration with mock provider
- Setup: successful run in `--json`
- Action: execute `nelson run ... --json`
- Expected result:
  - stdout contains exactly one valid JSON object
  - object matches [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
  - no progress noise is mixed into stdout

### T-OUT-003

- Level: integration with mock provider
- Setup: successful run in `--jsonl`
- Action: execute `nelson run ... --jsonl`
- Expected result:
  - stdout contains only JSON lines
  - every line validates against [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)

### T-OUT-004

- Level: integration with mock provider
- Setup: partial consensus in human mode
- Action: execute `nelson run ...`
- Expected result:
  - final output says consensus is partial
  - unresolved disagreement summary is shown

## 10. Live OpenRouter Smoke Tests

These tests are optional but recommended before declaring v1 usable.

Recommended v1 smoke-test matrix:

- participants: `openai/gpt-4.1-mini`, `google/gemini-2.5-flash-lite:nitro`
- moderator: `openai/gpt-4.1`

Rationale:

- keep participant cost low while preserving a stronger moderator role
- keep the live matrix aligned with officially documented OpenRouter structured-output support

### T-LIVE-001

- Level: live smoke
- Setup: valid `OPENROUTER_API_KEY`, use the recommended v1 smoke-test matrix
- Action: execute `nelson run` with one short analytical prompt in `--json`
- Expected result:
  - run succeeds or partial-succeeds without transport errors
  - usage metadata is populated if provider returns it

### T-LIVE-002

- Level: live smoke
- Setup: valid `OPENROUTER_API_KEY`, use the recommended v1 smoke-test matrix
- Action: execute `nelson run ... --jsonl`
- Expected result:
  - stream contains framing, candidate, and terminal run events in valid total order
  - structured internal phases may emit no `model_delta` events
  - stream terminates with `run_completed` or `run_failed`

## 11. Minimum Definition of Done

Nelson v1 should not be considered done until all of the following are true:

- all CLI validation tests pass
- auth flows pass in isolated temporary-home tests
- mock-provider consensus tests pass
- failure and repair tests pass
- event schema export works
- at least one live OpenRouter smoke test passes with a real key

## 12. References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
