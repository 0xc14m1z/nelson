# Nelson Application Protocol v1

## Purpose

This document defines the boundary between adapters and the Nelson core.

In Nelson v1:

- adapters submit typed application commands
- the core processes those commands
- the core emits typed events
- adapters render or consume those events

This is the architectural pattern that allows the CLI and a future UI to share the same communication protocol.

## Normative Language

The keywords below are used intentionally:

- `MUST`: mandatory rule
- `SHOULD`: strong default that may be overridden with explicit justification
- `MAY`: acceptable option

## Normative References

- [../PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)

## 1. Core Rule

Nelson adapters must not call orchestration logic directly.

Instead:

- adapters construct typed commands
- adapters dispatch those commands to the core
- the core emits typed events

The command/event boundary is mandatory for:

- CLI
- future UI
- any future local or remote adapter

## 2. Scope of the Protocol

The application protocol is an in-process protocol in v1.

That means:

- no Kafka
- no Redis
- no RabbitMQ
- no networked service bus requirement

The protocol is about architecture and contracts, not infrastructure.

In v1 the implementation may use:

- a dispatcher object
- an async generator
- an internal queue-backed stream

Any of those are acceptable as long as the public behavior matches this document.

## 3. Protocol Shape

The recommended conceptual shape is:

```python
class CommandExecution(Protocol):
    events: AsyncIterator[ApplicationEvent]
    result: Awaitable[CommandResult | None]

def dispatch(command: ApplicationCommand) -> CommandExecution:
    ...
```

The exact Python signature may vary, but the semantics must remain:

- one typed command in
- one ordered event stream out
- one optional typed terminal result out

`CommandResult` above is a conceptual union of command-specific terminal result types.

In v1 that conceptual union should include:

- `RunResult`
- `AuthSetResult`
- `AuthStatusResult`
- `AuthClearResult`

`events` is the canonical runtime protocol.

`result` exists so adapters do not have to reconstruct large terminal objects from event replay.

This split is intentional:

- streaming observers such as `--jsonl` stay event-first
- terminal materialization such as `nelson run --json` stays strongly typed
- the CLI remains thin rather than replaying events into a separate result builder

## 4. Command Model

Every command must have a typed model.

Each command must include at least:

- `command_id`
- `type`
- `issued_at`
- command-specific typed payload fields

Recommended common fields:

- `adapter`: `cli`, `ui`, or another adapter label
- `metadata`: optional structured metadata if later needed

## 5. Command Types Required in v1

Nelson v1 must define these command types:

- `AuthSetCommand`
- `AuthStatusCommand`
- `AuthClearCommand`
- `RunCommand`

### 5.1 `AuthSetCommand`

Required payload:

- `api_key`

### 5.2 `AuthStatusCommand`

Required payload:

- no command-specific payload fields beyond the common command fields

### 5.3 `AuthClearCommand`

Required payload:

- no command-specific payload fields beyond the common command fields

### 5.4 `RunCommand`

Required payload:

- `input_source`
- `prompt_text`
- `participants`
- `moderator`
- `max_rounds`
- `release_gate_mode`

Optional payload:

- `openrouter_api_key_override`

Notes:

- `prompt_text` should already be resolved by the adapter from `--prompt`, `--prompt-file`, or `--stdin`
- `input_source` should preserve where the prompt came from
- the core remains responsible for effective credential resolution

### 5.5 Terminal result semantics

For every successfully dispatched command, the core must expose one `CommandExecution`.

Rules:

- `CommandExecution.events` must begin streaming as soon as the command is accepted
- `CommandExecution.result` must resolve only after the command reaches a terminal state
- `RunCommand` must resolve `result` to a typed `RunResult`
- `AuthSetCommand` should resolve `result` to a typed `AuthSetResult`
- `AuthStatusCommand` should resolve `result` to a typed `AuthStatusResult`
- `AuthClearCommand` should resolve `result` to a typed `AuthClearResult`
- for `RunCommand`, `result` must be available for runtime `success`, `partial`, and runtime `failed` outcomes
- adapter-side failures before command construction or dispatch must not create a `CommandExecution`

Rationale:

- the event stream remains the canonical observability boundary
- the terminal `RunResult` remains the canonical materialized output for `--json`
- failed runtime executions still need a typed final object without forcing adapters to infer it from events
- auth commands also benefit from typed terminal state for tests and future adapters, but they do not need a separate public JSON schema in v1

### 5.6 Minimal auth result types

Auth result types should be documented here as part of the application protocol rather than in a separate top-level schema document.

Rationale:

- `run` has a public `--json` contract and needs its own dedicated schema document
- `auth` results are still useful internally and for future adapters
- documenting them here keeps the protocol coherent without inflating the public contract surface

Recommended minimal shapes:

#### `AuthSetResult`

```json
{
  "saved": true,
  "storage_path": "~/.nelson/openrouter_api_key"
}
```

#### `AuthStatusResult`

```json
{
  "saved_key_present": true,
  "env_key_present": false,
  "effective_source": "saved",
  "verification": "valid"
}
```

If verification metadata is available, the implementation may additionally include small typed fields such as:

- `key_label`
- `remaining_limit`
- `is_free_tier`

#### `AuthClearResult`

```json
{
  "saved_key_removed": true
}
```

## 6. Adapter Responsibilities

Adapters such as the CLI must handle:

- raw user interaction
- command-line argument parsing
- reading prompt text from file or stdin
- constructing the correct typed command
- dispatching the command through the application protocol
- rendering or consuming resulting events

Adapters must not handle:

- consensus logic
- provider routing logic
- release gate decisions
- event semantics beyond rendering

## 7. Core Responsibilities

The core must handle:

- command validation beyond interface parsing where needed
- credential resolution
- orchestration
- provider invocation
- consensus flow
- event emission
- final result materialization for commands that need one

## 8. Event Semantics

The application protocol uses one ordered stream of typed events.

There are two layers of events:

### 8.1 Application lifecycle events

These apply to all commands:

- `command_received`
- `command_completed`
- `command_failed`

### 8.2 Domain events

These depend on the command type.

For auth commands:

- `auth_key_saved`
- `auth_status_reported`
- `auth_key_cleared`

For run commands:

- all run lifecycle, progress, model, review, consensus, release-gate, and usage events defined in [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)

## 9. Ordering Rules

For every dispatched command:

1. `command_received` must be emitted first
2. zero or more command-specific domain events may follow
3. exactly one terminal application event must end the stream:
   - `command_completed`
   - `command_failed`

For `RunCommand`, run-specific events such as `run_started` and `run_completed` live inside that command stream.

## 10. Terminal Semantics

### 10.1 Successful auth commands

The stream should typically look like:

- `command_received`
- one auth domain event
- `command_completed`

### 10.2 Successful run command

The stream should typically look like:

- `command_received`
- `run_started`
- zero or more progress and domain events
- `run_completed`
- `command_completed`

If the run is partial but still yields a usable answer:

- `run_completed` should indicate partial status
- `command_completed` should still be used rather than `command_failed`

### 10.3 Failed command

If the command cannot complete successfully:

- emit `command_failed`
- include a typed structured error

For `RunCommand`, a failed run should also emit `run_failed` before the terminal `command_failed` where possible.

If a `RunCommand` fails at runtime, the existence of a materialized failed `RunResult` does not change the terminal event semantics:

- the run still emits `run_failed`
- the command still emits `command_failed`
- `CommandExecution.result` still resolves to a typed `RunResult` with `status = "failed"`

## 11. Relationship to CLI Output Modes

The application protocol exists regardless of CLI rendering mode.

### 11.1 Human mode

The CLI consumes events and renders:

- progress on `stderr`
- final user-facing output on `stdout`

### 11.2 JSON mode

For `RunCommand`, the CLI should await `CommandExecution.result` and emit the resulting `RunResult` object defined in [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md).

The CLI may still observe the event stream while the run is active, but it should not reconstruct the final JSON object purely from event replay.

### 11.3 JSONL mode

For `RunCommand`, the CLI emits the event stream directly as JSON Lines.

Auth commands do not need user-facing `--json` or `--jsonl` flags in v1, but they should still be implemented through the same application protocol internally.

## 12. Why This Pattern Exists

This pattern exists to preserve four important properties:

- the core stays headless
- the CLI stays thin
- future UIs can reuse the same protocol
- testing can operate at the command/event level without shell coupling

## 13. Non-Goals

This document does not require:

- a distributed bus
- a separate process boundary
- remote transport
- external event storage

Those may come later, but they are not required for v1.

## 14. Implementation Guidance

Recommended implementation approach:

- define Pydantic models for commands
- define Pydantic models for events
- define a typed `CommandExecution` wrapper or equivalent
- implement one dispatcher/service object
- make adapters depend on that dispatcher rather than on orchestration internals

If the implementation uses an internal queue or async generator, that is acceptable.

The important thing is the architectural contract, not the mechanism.

## 15. References

- [../PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)
