# Nelson Run Result Schema v1

## Purpose

This document defines the single-object result returned by `nelson run --json`.

It also defines the canonical failure object used in JSON mode.

This result should be treated as the terminal materialized result of a `RunCommand`.

## Normative References

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Limits and key metadata: <https://openrouter.ai/docs/api/reference/limits>

## 1. Top-Level Object

Nelson must always return exactly one JSON object in `--json` mode.

The top-level shape is:

```json
{
  "run_id": "run_...",
  "status": "success",
  "error": null,
  "input": {},
  "models": {},
  "task_framing": {},
  "consensus": {},
  "release_gate": {},
  "final_answer": "string",
  "usage": {},
  "timing": {}
}
```

## 2. Top-Level Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `run_id` | string or null | yes | Null only if a fatal pre-dispatch serialization failure occurs, which should be rare |
| `status` | string | yes | `success`, `partial`, or `failed` |
| `error` | object or null | yes | Populated only when `status = failed` |
| `input` | object | yes | Prompt source metadata |
| `models` | object | yes | Participants and moderator |
| `task_framing` | object or null | yes | Null only if the run fails before framing completes |
| `consensus` | object | yes | Consensus outcome metadata |
| `release_gate` | object | yes | Release gate mode and result |
| `final_answer` | string or null | yes | Null only when `status = failed` |
| `usage` | object | yes | Invocation and aggregate usage snapshots |
| `timing` | object | yes | Timing metadata |

## 3. Enums

### 3.1 `status`

- `success`
- `partial`
- `failed`

### 3.2 `input.source`

- `prompt`
- `prompt_file`
- `stdin`

### 3.3 `task_framing.task_type`

- `factual`
- `comparative`
- `analytical`
- `creative`
- `advice`
- `planning`
- `classification`
- `transformation`
- `other`

### 3.4 `task_framing.sensitivity`

- `low`
- `medium`
- `high`

### 3.5 `consensus.status`

- `reached`
- `partial`
- `failed`

### 3.6 `release_gate.mode`

- `off`
- `auto`
- `on`

### 3.7 `release_gate.decision`

- `skipped`
- `pass`
- `pass_with_minor_fixes`
- `fail`

## 4. `input`

```json
{
  "source": "prompt",
  "prompt_chars": 128,
  "prompt_file": null
}
```

Rules:

- `prompt_file` is populated only when `source = "prompt_file"`.
- The raw prompt text itself should not be echoed by default in v1 JSON output.

## 5. `models`

```json
{
  "participants": [
    "openai/gpt-4.1",
    "anthropic/claude-3.7-sonnet"
  ],
  "moderator": "openai/gpt-4.1",
  "excluded_participants": [
    {
      "model": "anthropic/claude-3.7-sonnet",
      "round_excluded": 2,
      "reason_code": "structured_output_repair_failed",
      "reason_summary": "Participant excluded after invalid structured output and failed repair",
      "failed_invocation_id": "inv_014"
    }
  ]
}
```

Rules:

- `participants` is the originally configured participant list
- `excluded_participants` must always be present, even when empty
- `excluded_participants` records participants permanently removed from the active set during the run
- a non-empty `excluded_participants` array does not by itself force `status = "partial"` if quorum remained valid and consensus was reached

## 6. `task_framing`

```json
{
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

Rules:

- `task_framing` stores only the final effective framing snapshot
- framing history does not appear in `RunResult` in v1
- if framing was updated during the run, the event stream remains the canonical audit trail for earlier versions

## 7. `consensus`

```json
{
  "status": "reached",
  "rounds_completed": 2,
  "max_rounds": 10,
  "minor_revisions_applied": [
    "Clarified packaging guidance"
  ],
  "blocking_issues_resolved": [
    "Removed unsupported claim about deployment tooling"
  ],
  "residual_disagreements": []
}
```

Rules:

- `status = "reached"` when no `major_revise` or `reject` remains.
- `status = "partial"` when Nelson returns the best candidate after exhausting rounds.
- `status = "failed"` only when no usable final answer can be produced.
- `status = "reached"` may coexist with participant exclusions if quorum was preserved and closure rules were satisfied.

## 8. `release_gate`

```json
{
  "mode": "auto",
  "executed": true,
  "decision": "pass_with_minor_fixes",
  "summary": "Added a caveat about context dependence",
  "minor_fixes_applied": [
    "Added caveat about deployment context"
  ],
  "blocking_issues": []
}
```

Rules:

- `decision = "skipped"` when release gate is not executed.
- `executed = false` implies `decision = "skipped"`.

## 9. `usage`

```json
{
  "per_invocation": [
    {
      "invocation_id": "inv_001",
      "model": "openai/gpt-4.1",
      "role": "moderator",
      "purpose": "task_framing",
      "prompt_tokens": 450,
      "completion_tokens": 120,
      "total_tokens": 570,
      "cost_usd": null,
      "currency": "USD",
      "is_normalized": true,
      "is_complete": true
    }
  ],
  "total": {
    "prompt_tokens": 2400,
    "completion_tokens": 1100,
    "total_tokens": 3500,
    "cost_usd": null,
    "currency": "USD",
    "is_normalized": true,
    "is_complete": true
  }
}
```

Notes:

- In v1, token counts may reflect provider-reported normalized usage rather than exact native-token accounting.
- `cost_usd` is optional and may be null.
- per-invocation entries should still be included when usage is unknown; in that case numeric fields may be `null` and `is_complete` must be `false`
- `usage.total` must include all known usage from successful calls, failed calls, retries, repairs, and invocations belonging to participants later excluded from the run
- `usage.total.is_complete` must be `false` whenever any invocation-level usage needed for a complete aggregate total is unavailable

## 10. `timing`

```json
{
  "started_at": "2026-03-09T12:34:56.789Z",
  "completed_at": "2026-03-09T12:35:14.123Z",
  "duration_ms": 17334
}
```

## 11. `error`

When `status = "failed"`, `error` must be populated:

```json
{
  "code": "participant_quorum_lost",
  "message": "Only one valid participant remained after retries",
  "phase": "participant_review",
  "retryable": false,
  "details": {}
}
```

Recommended fields:

| Field | Type | Required |
| --- | --- | --- |
| `code` | string | yes |
| `message` | string | yes |
| `phase` | string | yes |
| `retryable` | boolean | yes |
| `details` | object | yes |

## 12. Canonical Success Example

```json
{
  "run_id": "run_01HXYZ",
  "status": "success",
  "error": null,
  "input": {
    "source": "prompt",
    "prompt_chars": 73,
    "prompt_file": null
  },
  "models": {
    "participants": [
      "openai/gpt-4.1",
      "anthropic/claude-3.7-sonnet"
    ],
    "moderator": "openai/gpt-4.1",
    "excluded_participants": []
  },
  "task_framing": {
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
  },
  "consensus": {
    "status": "reached",
    "rounds_completed": 2,
    "max_rounds": 10,
    "minor_revisions_applied": [
      "Clarified packaging guidance"
    ],
    "blocking_issues_resolved": [
      "Removed unsupported claim about deployment tooling"
    ],
    "residual_disagreements": []
  },
  "release_gate": {
    "mode": "auto",
    "executed": true,
    "decision": "pass_with_minor_fixes",
    "summary": "Added a caveat about context dependence",
    "minor_fixes_applied": [
      "Added caveat about deployment context"
    ],
    "blocking_issues": []
  },
  "final_answer": "A good Python application should emphasize clarity, testability, packaging discipline, and explicit operational assumptions...",
  "usage": {
    "per_invocation": [],
    "total": {
      "prompt_tokens": 2400,
      "completion_tokens": 1100,
      "total_tokens": 3500,
      "cost_usd": null,
      "currency": "USD",
      "is_normalized": true,
      "is_complete": true
    }
  },
  "timing": {
    "started_at": "2026-03-09T12:34:56.789Z",
    "completed_at": "2026-03-09T12:35:14.123Z",
    "duration_ms": 17334
  }
}
```

## 13. Canonical Partial Example

```json
{
  "run_id": "run_01HXYZ",
  "status": "partial",
  "error": null,
  "input": {
    "source": "prompt",
    "prompt_chars": 91,
    "prompt_file": null
  },
  "models": {
    "participants": [
      "openai/gpt-4.1",
      "anthropic/claude-3.7-sonnet"
    ],
    "moderator": "openai/gpt-4.1",
    "excluded_participants": []
  },
  "task_framing": {
    "task_type": "comparative",
    "sensitivity": "low",
    "objective": "Recommend and compare stadiums",
    "quality_criteria": [
      "accuracy",
      "clear justification"
    ],
    "aspects_to_cover": [
      "fan experience",
      "historical significance"
    ],
    "ambiguities": [
      "Best may be subjective"
    ],
    "assumptions": [],
    "framing_version": 1
  },
  "consensus": {
    "status": "partial",
    "rounds_completed": 10,
    "max_rounds": 10,
    "minor_revisions_applied": [],
    "blocking_issues_resolved": [],
    "residual_disagreements": [
      "One participant wanted stronger qualification around subjectivity"
    ]
  },
  "release_gate": {
    "mode": "auto",
    "executed": true,
    "decision": "pass",
    "summary": "Answer is deliverable despite residual subjectivity disagreement",
    "minor_fixes_applied": [],
    "blocking_issues": []
  },
  "final_answer": "The best baseball stadiums in Finland depend on whether you prioritize competitive quality, history, or spectator atmosphere...",
  "usage": {
    "per_invocation": [],
    "total": {
      "prompt_tokens": 4100,
      "completion_tokens": 2200,
      "total_tokens": 6300,
      "cost_usd": null,
      "currency": "USD",
      "is_normalized": true,
      "is_complete": true
    }
  },
  "timing": {
    "started_at": "2026-03-09T12:34:56.789Z",
    "completed_at": "2026-03-09T12:36:21.123Z",
    "duration_ms": 84334
  }
}
```

## 14. Canonical Failure Example

```json
{
  "run_id": "run_01HXYZ",
  "status": "failed",
  "error": {
    "code": "participant_quorum_lost",
    "message": "Only one valid participant remained after retries",
    "phase": "participant_review",
    "retryable": false,
    "details": {}
  },
  "input": {
    "source": "prompt",
    "prompt_chars": 91,
    "prompt_file": null
  },
  "models": {
    "participants": [
      "openai/gpt-4.1",
      "anthropic/claude-3.7-sonnet"
    ],
    "moderator": "openai/gpt-4.1",
    "excluded_participants": [
      {
        "model": "anthropic/claude-3.7-sonnet",
        "round_excluded": 1,
        "reason_code": "structured_output_repair_failed",
        "reason_summary": "Participant excluded after invalid structured output and failed repair",
        "failed_invocation_id": "inv_008"
      }
    ]
  },
  "task_framing": {
    "task_type": "comparative",
    "sensitivity": "low",
    "objective": "Recommend and compare stadiums",
    "quality_criteria": [
      "accuracy"
    ],
    "aspects_to_cover": [
      "spectator experience"
    ],
    "ambiguities": [],
    "assumptions": [],
    "framing_version": 1
  },
  "consensus": {
    "status": "failed",
    "rounds_completed": 1,
    "max_rounds": 10,
    "minor_revisions_applied": [],
    "blocking_issues_resolved": [],
    "residual_disagreements": []
  },
  "release_gate": {
    "mode": "auto",
    "executed": false,
    "decision": "skipped",
    "summary": "Run failed before release gate",
    "minor_fixes_applied": [],
    "blocking_issues": []
  },
  "final_answer": null,
  "usage": {
    "per_invocation": [],
    "total": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0,
      "cost_usd": null,
      "currency": "USD",
      "is_normalized": true,
      "is_complete": false
    }
  },
  "timing": {
    "started_at": "2026-03-09T12:34:56.789Z",
    "completed_at": "2026-03-09T12:35:01.123Z",
    "duration_ms": 4334
  }
}
```

## 15. References

- [APPLICATION_PROTOCOL.md](./APPLICATION_PROTOCOL.md)
- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [PROMPT_SPEC.md](./PROMPT_SPEC.md)
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Limits and key metadata: <https://openrouter.ai/docs/api/reference/limits>
