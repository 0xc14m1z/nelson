# Nelson CLI Specification v1

## Purpose

This document defines the CLI behavior required for Nelson v1.

It is written so that an implementation agent can build the CLI without needing to invent command semantics, exit-code behavior, or output contracts.

## Normative References

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Authentication: <https://openrouter.ai/docs/api/reference/authentication>
- OpenRouter Limits and key metadata: <https://openrouter.ai/docs/api/reference/limits>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Chat Completions: <https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request>

## 1. CLI Surface

Nelson v1 exposes exactly these command groups:

- `nelson auth set --api-key <KEY>`
- `nelson auth status`
- `nelson auth clear`
- `nelson run ...`

No other user-facing commands are required in v1.

## 1.1 Application command mapping

The CLI is an adapter over the application protocol.

The CLI must translate user-facing commands into typed application commands:

- `nelson auth set --api-key <KEY>` -> `AuthSetCommand`
- `nelson auth status` -> `AuthStatusCommand`
- `nelson auth clear` -> `AuthClearCommand`
- `nelson run ...` -> `RunCommand`

The CLI must not bypass the application layer and call orchestration logic directly.

## 2. Global Rules

### 2.1 Output modes

`nelson run` supports exactly three output modes:

- human-readable default
- `--json`
- `--jsonl`

`--json` and `--jsonl` are mutually exclusive.

If both are provided, the command fails with exit code `2`.

### 2.2 Standard streams

#### Human mode

- Progress and status updates should be written to `stderr`.
- The final human-readable answer block should be written to `stdout`.
- Fatal command errors should be written to `stderr`.

This split keeps the CLI usable interactively while remaining tolerable in shell pipelines.

#### `--json`

- `stdout` must contain exactly one JSON document.
- `stderr` must not contain non-fatal progress noise.
- If the command fails after parsing begins, the failure must still be rendered as one JSON document matching the failure contract in [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md).

#### `--jsonl`

- `stdout` must contain only JSON Lines events.
- `stderr` must not contain non-fatal progress noise.
- If the command fails after `run` command dispatch begins, the failure must be emitted as a `run_failed` event matching [EVENT_SCHEMA.md](./EVENT_SCHEMA.md).

### 2.3 Text encoding

- Prompt files must be read as UTF-8 text.
- `stdin` must be read as UTF-8 text.
- Nelson should preserve prompt text as-is and must not trim or normalize user content beyond standard end-of-file reading.

## 3. Exit Codes

Nelson v1 must use these exit codes consistently.

| Exit code | Meaning |
| --- | --- |
| `0` | Command succeeded |
| `2` | Invalid CLI usage or invalid user input |
| `3` | Missing credentials or credential storage error |
| `4` | Credential verification failed or provider returned authentication/authorization failure |
| `5` | Provider transport/runtime failure prevented completion |
| `6` | Orchestration failure after startup, including quorum loss or moderator failure |
| `7` | Serialization or output rendering failure |
| `130` | Interrupted by user |

Notes:

- `auth status` should return `0` only when an effective key is found and verified successfully.
- `auth status` should return `3` when no effective key is available.
- `auth status` should return `4` when a key exists but verification fails.

## 4. Credential Resolution

Nelson must resolve credentials for `run` in this order:

1. `--openrouter-api-key`
2. `OPENROUTER_API_KEY`
3. saved key in `~/.nelson/openrouter_api_key`

`auth status` must inspect the effective key using the same order, excluding the CLI override because no override is accepted by that subcommand.

`auth clear` only removes the saved key file. It does not and cannot affect environment variables.

## 5. `auth` Command Group

### 5.1 `auth set`

#### Syntax

```bash
nelson auth set --api-key <KEY>
```

#### Rules

- `--api-key` is required.
- Nelson must create `~/.nelson/` if it does not exist.
- The saved file path is `~/.nelson/openrouter_api_key`.
- The saved file should be written with restrictive user-only permissions.
- Overwriting an existing saved key is allowed.

#### Human success output

Recommended stdout message:

```text
Saved OpenRouter API key to ~/.nelson/openrouter_api_key
```

#### Errors

- invalid or missing `--api-key` argument: exit `2`
- unable to create directory or write file: exit `3`

### 5.2 `auth status`

#### Syntax

```bash
nelson auth status
```

#### Verification behavior

`auth status` must:

1. detect whether a key is available from env or saved file
2. identify the effective source
3. verify the effective key against OpenRouter

The verification call should use `GET https://openrouter.ai/api/v1/key`, as documented by OpenRouter for checking credits and limits on an API key.

#### Human output

Human output should include at least:

- saved key status: `present` or `absent`
- environment key status: `present` or `absent`
- effective source: `env`, `saved`, or `none`
- verification: `valid`, `invalid`, or `not_checked`

If verification succeeds and OpenRouter returns metadata, Nelson may additionally show:

- key label
- remaining limit if present
- whether the key is free tier if present

Nelson must never print the full key.

#### Exit behavior

- effective key missing: exit `3`
- effective key present and valid: exit `0`
- effective key present but invalid or unauthorized: exit `4`

### 5.3 `auth clear`

#### Syntax

```bash
nelson auth clear
```

#### Behavior

- If the saved key file exists, delete it.
- If the saved key file does not exist, the command still succeeds.

#### Exit behavior

- success or already absent: exit `0`
- filesystem error while deleting: exit `3`

## 6. `run` Command

### 6.1 Syntax

Example:

```bash
nelson run \
  --participant openai/gpt-4.1 \
  --participant anthropic/claude-3.7-sonnet \
  --moderator openai/gpt-4.1 \
  --prompt "What are the main principles for building a Python application?" \
  --max-rounds 10 \
  --release-gate auto
```

### 6.2 Required arguments

- at least two `--participant` flags
- one `--moderator`
- exactly one prompt source:
  - `--prompt`
  - `--prompt-file`
  - `--stdin`

### 6.3 Optional arguments

- `--max-rounds <int>` default `10`
- `--openrouter-api-key <KEY>`
- `--release-gate <off|auto|on>` default `auto`
- `--json`
- `--jsonl`

### 6.4 Validation rules

The command must fail with exit code `2` if any of the following are true:

- fewer than two participant flags are provided
- `--moderator` is omitted
- no prompt source is provided
- more than one prompt source is provided
- both `--json` and `--jsonl` are provided
- `--max-rounds` is not a positive integer
- a prompt file path does not exist or is unreadable
- participant list contains duplicate model ids
- a participant model id is empty
- moderator model id is empty

Notes:

- The moderator may be the same model id as one of the participants.
- Duplicate participant ids are disallowed in v1 to avoid ambiguous participant identity and redundant orchestration.

### 6.5 Run startup order

The implementation should follow this startup order:

1. parse CLI args
2. validate output mode and prompt-source rules
3. resolve prompt text
4. construct a `RunCommand`
5. dispatch the command through the application protocol
6. allow the core to resolve credentials and execute the run

In `--jsonl` mode, if failure occurs after command dispatch begins, a `command_failed` event should be emitted, and a `run_failed` event should also be emitted if the run had already started.

If failure occurs before command construction and dispatch, the CLI must fail locally without emitting application-protocol events.

## 7. Human Output Contract

### 7.1 Progress

Human mode must show compact progress updates to `stderr`.

Recommended format:

```text
Round 2/10 · review · 1/3 complete · est. 34%
```

### 7.2 Final answer block

The final human output written to `stdout` should contain:

1. the final answer
2. a one-line consensus status
3. if partial consensus, a short disagreement summary
4. if minor revisions were incorporated, a short note listing them

Model identities must not be shown in human mode by default.

## 8. JSON Output Contract

### 8.1 Success and partial success

`--json` must output one JSON object matching [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md).

The JSON object should come from the core's terminal `RunResult`, not from adapter-side reconstruction of the event stream.

### 8.2 Failure shape

If the run fails after command dispatch starts, `--json` must still output one JSON object with:

- `status: "failed"`
- `final_answer: null`
- `error` populated

### 8.3 No extra output

In `--json` mode, Nelson must not interleave human progress text on `stdout`.

## 9. JSONL Output Contract

### 9.1 Event-only stdout

`--jsonl` stdout must contain only events defined in [EVENT_SCHEMA.md](./EVENT_SCHEMA.md).

### 9.2 Failure behavior

On runtime failure after startup, Nelson must emit a terminal `run_failed` event before exiting non-zero.

### 9.3 Event ordering

All events must be emitted in a single total order using the `sequence` field.

## 10. Recommended Error Codes in Payloads

Where a structured error object is needed, v1 should use one of these stable symbolic codes:

- `invalid_arguments`
- `invalid_input_source`
- `missing_credentials`
- `credential_storage_error`
- `credential_verification_failed`
- `provider_auth_error`
- `provider_transport_error`
- `provider_timeout`
- `participant_failed`
- `participant_quorum_lost`
- `framing_update_budget_exhausted`
- `moderator_failed`
- `structured_output_invalid`
- `structured_output_repair_failed`
- `serialization_failed`
- `interrupted`

These symbolic codes are independent from process exit codes.

## 11. Implementation Notes

- `Typer` should be used for CLI parsing.
- The CLI must communicate with the core through typed application commands.
- Human rendering should be a thin adapter over the event stream, not a separate orchestration path.
- The CLI should never own consensus logic.

## 12. References

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Authentication: <https://openrouter.ai/docs/api/reference/authentication>
- OpenRouter Limits and key metadata: <https://openrouter.ai/docs/api/reference/limits>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
