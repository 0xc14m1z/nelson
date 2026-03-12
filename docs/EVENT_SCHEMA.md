# Nelson Event Schema v1

## Purpose

This document defines the typed event protocol emitted by the Nelson core and consumed by:

- the human CLI renderer
- `--jsonl`
- future UI adapters
- future agent integrations

This document is normative for the event contract.

## Normative References

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Streaming: <https://openrouter.ai/docs/api/reference/streaming>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Structured Outputs: <https://openrouter.ai/docs/features/structured-outputs>

## 1. Envelope

Every event must contain this envelope:

```json
{
  "event_id": "evt_...",
  "command_id": "cmd_...",
  "run_id": null,
  "sequence": 1,
  "timestamp": "2026-03-09T12:34:56.789Z",
  "type": "command_received",
  "phase": "command",
  "round": null,
  "role": "system",
  "model": null,
  "payload": {}
}
```

### 1.1 Required envelope fields

| Field | Type | Notes |
| --- | --- | --- |
| `event_id` | string | Unique event identifier |
| `command_id` | string | Stable identifier for the command execution |
| `run_id` | string or null | Stable identifier for the run, null for non-run commands |
| `sequence` | integer | Monotonic total-order sequence starting at `1` |
| `timestamp` | string | ISO 8601 UTC timestamp |
| `type` | string | One of the event types defined below |
| `phase` | string | One of the phase enums defined below |
| `round` | integer or null | `null` for non-round events |
| `role` | string | `system`, `participant`, or `moderator` |
| `model` | string or null | Null for system-level events |
| `payload` | object | Typed per `type` |

Framing version is intentionally not part of the common envelope in v1.

Instead, it appears only in payloads of framing-correlated events. This keeps infrastructure and telemetry events compact while still exposing framing context where it changes domain meaning.

## 2. Enums

### 2.1 Phase enum

- `command`
- `auth`
- `startup`
- `task_framing`
- `participant_generation`
- `candidate_synthesis`
- `participant_review`
- `release_gate`
- `finalization`
- `error`

### 2.2 Role enum

- `system`
- `participant`
- `moderator`

### 2.3 Event type enum

- `command_received`
- `command_completed`
- `command_failed`
- `auth_key_saved`
- `auth_status_reported`
- `auth_key_cleared`
- `run_started`
- `run_completed`
- `run_failed`
- `progress_updated`
- `consensus_pending`
- `consensus_reached`
- `consensus_partial`
- `task_framing_started`
- `task_framing_completed`
- `task_framing_updated`
- `model_started`
- `model_delta`
- `model_completed`
- `model_failed`
- `participant_excluded`
- `round_started`
- `round_completed`
- `candidate_created`
- `candidate_updated`
- `review_started`
- `review_completed`
- `release_gate_started`
- `release_gate_completed`
- `usage_reported`

### 2.4 Purpose enum for model invocations

- `task_framing`
- `initial_contribution`
- `reframed_contribution`
- `candidate_synthesis`
- `candidate_review`
- `release_gate`
- `repair`

## 3. Shared Typed Fragments

### 3.1 Usage snapshot

```json
{
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "cost_usd": null,
  "currency": "USD",
  "is_normalized": true,
  "is_complete": true
}
```

Notes:

- `cost_usd` is optional and may be null in v1.
- `is_normalized` should be `true` when usage comes from provider-reported normalized tokens.
- token fields may be `null` when the provider does not return usage for that scope.
- `is_complete` indicates whether the snapshot is complete for the scope it represents.

### 3.2 Error object

```json
{
  "code": "provider_timeout",
  "message": "OpenRouter request timed out after 60s",
  "retryable": true,
  "details": {}
}
```

## 4. Event Payloads

### 4.0 `command_received`

```json
{
  "command_type": "run",
  "adapter": "cli"
}
```

`command_type` must be one of:

- `auth_set`
- `auth_status`
- `auth_clear`
- `run`

### 4.0b `command_completed`

```json
{
  "command_type": "run",
  "status": "success"
}
```

`status` must be one of:

- `success`
- `partial`

### 4.0c `command_failed`

```json
{
  "command_type": "run",
  "error": {
    "code": "participant_quorum_lost",
    "message": "Only one valid participant remained after retries",
    "retryable": false,
    "details": {}
  }
}
```

### 4.0d `auth_key_saved`

```json
{
  "storage_path": "~/.nelson/openrouter_api_key"
}
```

### 4.0e `auth_status_reported`

```json
{
  "saved_key_present": true,
  "env_key_present": false,
  "effective_source": "saved",
  "verification": "valid"
}
```

### 4.0f `auth_key_cleared`

```json
{
  "saved_key_removed": true
}
```

### 4.1 `run_started`

```json
{
  "input_source": "prompt",
  "max_rounds": 10,
  "release_gate_mode": "auto",
  "participants": [
    "openai/gpt-4.1",
    "anthropic/claude-3.7-sonnet"
  ],
  "moderator": "openai/gpt-4.1"
}
```

### 4.2 `run_completed`

```json
{
  "status": "success",
  "rounds_completed": 2,
  "consensus_status": "reached",
  "framing_version": 1,
  "final_answer_chars": 1248,
  "duration_ms": 18342
}
```

`status` may be `success` or `partial`.

`framing_version` is the final effective framing version for the run.

### 4.3 `run_failed`

```json
{
  "status": "failed",
  "framing_version": 1,
  "error": {
    "code": "moderator_failed",
    "message": "Moderator could not complete release gate after retry",
    "retryable": false,
    "details": {}
  }
}
```

`framing_version` should be the last effective framing version for the run, or `null` if the run failed before any framing version became effective.

### 4.4 `progress_updated`

```json
{
  "phase_name": "participant_review",
  "phase_index": 5,
  "phase_count_estimate": 7,
  "round": 2,
  "max_rounds": 10,
  "completed_units": 1,
  "total_units": 3,
  "stage_progress": 0.33,
  "overall_progress_estimate": 0.34,
  "is_estimate": true,
  "message": "Reviewing moderator candidate"
}
```

### 4.5 `consensus_pending`

```json
{
  "candidate_id": "cand_02",
  "reviewer_count": 2,
  "blocking_review_count": 1,
  "minor_revise_count": 1,
  "major_revise_count": 1,
  "reject_count": 0,
  "summary": "One blocking issue remains"
}
```

### 4.6 `consensus_reached`

```json
{
  "candidate_id": "cand_03",
  "reviewer_count": 3,
  "approve_count": 2,
  "minor_revise_count": 1,
  "major_revise_count": 0,
  "reject_count": 0,
  "summary": "No blocking objections remain"
}
```

### 4.7 `consensus_partial`

```json
{
  "candidate_id": "cand_05",
  "reason": "max_rounds_exhausted",
  "unresolved_issues": [
    "One participant believes the answer should include stronger caveats"
  ]
}
```

### 4.8 `task_framing_started`

```json
{
  "invocation_id": "inv_001",
  "schema_name": "TaskFraming",
  "streaming": true
}
```

### 4.9 `task_framing_completed`

```json
{
  "invocation_id": "inv_001",
  "task_type": "analytical",
  "sensitivity": "low",
  "objective": "Provide a complete and accurate answer to the user's request",
  "quality_criteria": [
    "accuracy",
    "coverage",
    "clarity"
  ],
  "aspects_to_cover": [
    "architecture",
    "testing",
    "packaging"
  ],
  "ambiguities": [],
  "assumptions": [],
  "framing_version": 1
}
```

Initial framing always starts at `framing_version = 1`.

### 4.9b `task_framing_updated`

```json
{
  "task_type": "analytical",
  "sensitivity": "medium",
  "objective": "Provide a complete and accurate answer to the user's request",
  "quality_criteria": [
    "accuracy",
    "coverage",
    "clarity"
  ],
  "aspects_to_cover": [
    "architecture",
    "testing",
    "deployment caveats"
  ],
  "ambiguities": [],
  "assumptions": [],
  "framing_version": 2,
  "previous_framing_version": 1,
  "effective_from_round": 3,
  "invalidated_candidate_id": "cand_02",
  "update_reason": "A material framing issue was identified around deployment caveats"
}
```

Rules:

- `task_framing_updated` must be emitted only for material framing changes
- its envelope `phase` must always be `task_framing`
- its envelope `round` must refer to the round that discovered the framing problem
- the new framing takes effect only from `effective_from_round`
- when this event is emitted, the invalidated candidate must not receive `review_*` or `consensus_*` events

Rationale:

- a dedicated event keeps initial framing and later reframing semantically distinct
- a full framing snapshot avoids forcing consumers to replay deltas to understand current state

### 4.10 `model_started`

```json
{
  "invocation_id": "inv_002",
  "purpose": "initial_contribution",
  "framing_version": 1,
  "schema_name": "ParticipantInitialContribution",
  "streaming": true,
  "retry_index": 0
}
```

Rules:

- `framing_version` must be included for all purposes except the initial `task_framing` invocation, where it may be null
- `repair_of_invocation_id` must be included when `purpose = "repair"`
- retries must use a new `invocation_id`; `retry_index` links attempts belonging to the same logical operation

### 4.11 `model_delta`

```json
{
  "invocation_id": "inv_002",
  "delta_index": 12,
  "text": "Testing is not optional in Python applications...",
  "is_structured_output": false
}
```

Rules:

- Emit only actual content deltas.
- Ignore provider SSE comment frames and keepalive frames.
- `text` may be empty only if the provider emits a completion chunk with no text but meaningful metadata. In that case the implementation may suppress the event entirely in v1.
- internal structured-output phases should not emit `model_delta` in v1
- `model_delta` is reserved for text-bearing streaming output where incremental text is useful to downstream consumers

### 4.12 `model_completed`

```json
{
  "invocation_id": "inv_002",
  "purpose": "initial_contribution",
  "framing_version": 1,
  "finish_reason": "stop",
  "output_format": "structured",
  "parsed": {
    "answer_markdown": "..."
  }
}
```

`output_format` must be one of:

- `text`
- `structured`

Rules:

- successful structured outputs should omit `raw_text` in v1
- `raw_text` may be included for `text` outputs
- repair invocations must include `repair_of_invocation_id`

### 4.13 `model_failed`

```json
{
  "invocation_id": "inv_002",
  "purpose": "candidate_review",
  "framing_version": 1,
  "retry_index": 1,
  "error": {
    "code": "structured_output_invalid",
    "message": "Model output did not validate against the required schema",
    "retryable": false,
    "details": {}
  }
}
```

Rules:

- invalid structured output from the original invocation must be represented as `model_failed`, not `model_completed`
- repair invocations use a new `invocation_id` and must include `repair_of_invocation_id`

### 4.13b `participant_excluded`

```json
{
  "reason_code": "structured_output_repair_failed",
  "reason_summary": "Participant excluded after invalid structured output and failed repair",
  "failed_invocation_id": "inv_014",
  "remaining_active_participant_count": 2,
  "quorum_preserved": true
}
```

Rules:

- the envelope `role` must be `participant`
- the envelope `model` must be the excluded participant model id
- the envelope `phase` must reflect the current runtime phase where exclusion occurred
- the event must be emitted immediately after the terminal failed invocation that caused permanent exclusion

Rationale:

- `model_failed` describes a failed invocation
- `participant_excluded` describes the effect of that failure on the run's active set

### 4.14 `round_started`

```json
{
  "round": 2,
  "candidate_id": "cand_02",
  "framing_version": 1,
  "target_participant_count": 3
}
```

`target_participant_count` is the point-in-time target at round start and must not be retroactively rewritten if the active set shrinks later in the round.

### 4.15 `round_completed`

```json
{
  "round": 2,
  "candidate_id": "cand_02",
  "framing_version": 1,
  "review_executed": true,
  "approve_count": 1,
  "minor_revise_count": 1,
  "major_revise_count": 1,
  "reject_count": 0,
  "candidate_invalidated_by_framing_update": false,
  "will_continue": true
}
```

Rules:

- if `review_executed = false`, all review-count fields must be `null`
- `candidate_invalidated_by_framing_update = true` means the round was closed after a material reframing and no review occurred
- a round invalidated by reframing still counts toward `rounds_completed`
- if the run fails immediately because quorum is lost mid-round, `round_completed` must not be emitted

### 4.16 `candidate_created`

```json
{
  "candidate_id": "cand_01",
  "framing_version": 1,
  "source": "initial_synthesis",
  "text": "Here is the synthesized answer...",
  "summary": "Initial moderator synthesis from participant responses",
  "excerpt_count": 3
}
```

`source` must be one of:

- `initial_synthesis`
- `major_revise_cycle`
- `minor_revise_incorporation`
- `release_gate_fix`

### 4.17 `candidate_updated`

```json
{
  "candidate_id": "cand_02",
  "previous_candidate_id": "cand_01",
  "framing_version": 1,
  "source": "major_revise_cycle",
  "text": "Updated candidate answer...",
  "summary": "Added stronger caveats and removed unsupported claim"
}
```

### 4.18 `review_started`

```json
{
  "candidate_id": "cand_02",
  "framing_version": 1,
  "target_participant_count": 3
}
```

### 4.19 `review_completed`

```json
{
  "candidate_id": "cand_02",
  "framing_version": 1,
  "reviewer_count": 3,
  "approve_count": 1,
  "minor_revise_count": 1,
  "major_revise_count": 1,
  "reject_count": 0,
  "blocking_issue_summaries": [
    "One participant flagged an unsupported technical claim"
  ],
  "minor_improvement_summaries": [
    "Clarify packaging recommendation"
  ]
}
```

`reviewer_count` is the actual number of valid review outcomes considered for this candidate and may be lower than the earlier target if the active set shrank during review.

### 4.20 `release_gate_started`

```json
{
  "invocation_id": "inv_010",
  "mode": "auto",
  "candidate_id": "cand_03",
  "framing_version": 1
}
```

The release gate must not emit framing updates. If it discovers a framing problem, it should fail the release gate and let the run return to a normal consensus round if budget remains.

### 4.21 `release_gate_completed`

```json
{
  "invocation_id": "inv_010",
  "candidate_id": "cand_03",
  "framing_version": 1,
  "executed": true,
  "decision": "pass_with_minor_fixes",
  "summary": "Added a caveat about context dependence",
  "minor_fixes_applied": [
    "Added caveat about deployment context"
  ],
  "blocking_issues": []
}
```

### 4.22 `usage_reported`

```json
{
  "scope": "invocation",
  "invocation_id": "inv_002",
  "usage": {
    "prompt_tokens": 1200,
    "completion_tokens": 450,
    "total_tokens": 1650,
    "cost_usd": null,
    "currency": "USD",
    "is_normalized": true,
    "is_complete": true
  }
}
```

`scope` must be one of:

- `invocation`
- `run_total`

If `scope` is `run_total`, `invocation_id` must be null.

## 5. Ordering Rules

- `sequence` must strictly increase by `1` within a command stream.
- `command_received` must be the first event of a successful command dispatch.
- `command_completed` or `command_failed` must be terminal at the application-command level.
- `run_started` must be the first runtime event after successful startup.
- `run_completed` or `run_failed` must be terminal at the run-domain level within a `RunCommand` stream.
- `model_delta` events for a given `invocation_id` must appear between that invocation's `model_started` and `model_completed` or `model_failed`.
- `task_framing_updated` may be emitted in any consensus round, but only after a candidate exists for that round and only for material framing changes
- when `task_framing_updated` invalidates a candidate, no `review_started`, `review_completed`, or `consensus_*` event may be emitted for that candidate
- `task_framing_updated` ends the semantic usefulness of earlier framing-bound contributions; the next round must gather fresh contributions from all active participants under the new framing version
- `participant_excluded` must be emitted immediately after the failed invocation chain that caused permanent exclusion
- if `participant_excluded` causes quorum loss, `run_failed` must be emitted and `round_completed` must not be emitted for that interrupted round

## 6. JSONL Recommendations

- Emit one compact JSON object per line.
- Avoid pretty-printing.
- Preserve stable key names.

## 7. Schema Notes for Pydantic

Recommended implementation pattern:

- one envelope model
- one discriminated union keyed by `type`
- one payload model per event type

This avoids a large untyped `payload: dict`.

## 8. References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Streaming: <https://openrouter.ai/docs/api/reference/streaming>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Structured Outputs: <https://openrouter.ai/docs/features/structured-outputs>
