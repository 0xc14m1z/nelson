# Nelson Internal Prompt Specification v1

## Purpose

This document defines the internal prompt contracts for Nelson v1.

It does not require the exact final wording of every prompt to match this document line-for-line, but it does require the implemented prompts to preserve the behavior, structure, and schema obligations described here.

## Normative References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Structured Outputs: <https://openrouter.ai/docs/features/structured-outputs>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>

## 1. Prompting Strategy

### 1.1 Core principle

Nelson uses prompts to coordinate a multi-model workflow with typed internal artifacts.

The internal phases are:

1. moderator task framing
2. participant initial contribution
3. moderator candidate synthesis
4. participant candidate review
5. moderator release gate
6. repair prompt for invalid structured output

### 1.2 Structured output policy

For internal phases, the implementation should prefer strict structured output.

Recommended behavior:

1. If the selected model supports JSON schema structured output, use provider-enforced schema mode.
2. If provider-enforced schema is unavailable, instruct the model to return JSON only.
3. Validate locally with Pydantic.
4. If validation fails, trigger one repair attempt.

Nelson v1 should not depend on OpenRouter's response-healing plugin for correctness. Local validation and repair remain required.

## 2. Shared Behavioral Rules

All internal prompts should reinforce these rules where relevant:

- do not invent certainty where uncertainty exists
- challenge flawed framing when necessary
- separate blocking problems from optional improvements
- prefer concise, concrete structured output
- do not include markdown code fences around JSON
- do not include explanatory prose outside the requested schema

## 3. Shared Enums and Typed Shapes

### 3.1 Task type enum

- `factual`
- `comparative`
- `analytical`
- `creative`
- `advice`
- `planning`
- `classification`
- `transformation`
- `other`

### 3.2 Sensitivity enum

- `low`
- `medium`
- `high`

### 3.3 Framing feedback status enum

- `accept`
- `minor_issue`
- `major_issue`

### 3.4 Review decision enum

- `approve`
- `minor_revise`
- `major_revise`
- `reject`

## 4. Task Framing Prompt

### 4.1 Purpose

The moderator performs task framing before participant generation.

The goal is to create an internal map of the user request, not to answer the question directly.

### 4.2 Inputs

- raw user prompt
- runtime context:
  - `max_rounds`
  - `release_gate_mode`

### 4.3 Required output schema

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
    "..."
  ],
  "ambiguities": [
    "..."
  ],
  "assumptions": [
    "..."
  ]
}
```

### 4.4 Prompt intent

The moderator should be instructed to:

- classify the task
- estimate sensitivity
- identify what a good answer must accomplish
- identify likely aspects to cover
- identify ambiguity or context dependence
- avoid answering the prompt itself

## 5. Participant Contribution Prompt

### 5.1 Purpose

Each participant should generate a fresh answer proposal while also evaluating the moderator's framing.

The same schema is used for:

- `initial_contribution` in the first contribution round
- `reframed_contribution` after a material framing update

### 5.2 Inputs

- raw user prompt
- current task framing object
- participant role reminder

### 5.3 Required output schema

```json
{
  "answer_markdown": "Main answer proposal in natural language",
  "assumptions": [
    "..."
  ],
  "limitations": [
    "..."
  ],
  "framing_feedback": {
    "status": "accept",
    "notes": [],
    "proposed_aspects": []
  }
}
```

### 5.4 Prompt intent

The participant should be instructed to:

- answer the user's prompt directly
- state assumptions and limitations explicitly
- inspect the task framing
- flag major or minor issues in the framing
- suggest missing aspects only when relevant

If the contribution follows a material framing update, the participant should be instructed to answer from the new framing alone rather than trying to preserve obsolete earlier assumptions.

## 6. Moderator Candidate Synthesis Prompt

### 6.1 Purpose

The moderator synthesizes participant responses into a candidate answer.

### 6.2 Inputs

- raw user prompt
- current task framing
- participant initial contributions
- any framing feedback raised by participants
- current round number

### 6.3 Required output schema

```json
{
  "candidate_markdown": "Synthesized answer draft",
  "summary": "Short description of what changed or was combined",
  "relevant_excerpt_labels": [
    "response_a",
    "response_c"
  ],
  "framing_update": null
}
```

If the moderator decides framing must change materially, `framing_update` should contain a full replacement framing object; otherwise it should be null.

Rules:

- `framing_update` is for material framing changes only, not wording cleanup
- if `framing_update` is non-null, the current candidate is considered invalidated for review
- a non-null `framing_update` should cause the run to start a new contribution round under the new framing version

### 6.4 Prompt intent

The moderator should be instructed to:

- combine complementary strengths
- remove redundancy
- resolve conflicts where possible
- preserve justified caveats
- update framing only when participant objections are substantial

## 7. Participant Review Prompt

### 7.1 Purpose

Participants review the moderator candidate and determine whether the answer is ready, needs minor revision, needs major revision, or should be rejected.

### 7.2 Inputs

- raw user prompt
- current task framing
- current moderator candidate
- moderator summary of prior contributions
- anonymized excerpts from other participants, labeled as `response_a`, `response_b`, and so on

### 7.3 Required output schema

```json
{
  "decision": "major_revise",
  "summary": "One core technical claim is unsupported",
  "required_changes": [
    "Remove or qualify the unsupported claim about deployment defaults"
  ],
  "optional_improvements": [
    "Clarify packaging recommendation"
  ],
  "blocking_issues": [
    "The answer states a universal rule that depends on context"
  ]
}
```

### 7.4 Prompt intent

The participant should be instructed to:

- judge the candidate against the user's prompt, not against stylistic preference
- use `minor_revise` only for non-blocking improvements
- use `major_revise` for substantive but recoverable problems
- use `reject` only when the candidate is materially wrong or misaligned
- avoid restating the whole answer
- focus on changes that matter

## 8. Moderator Release Gate Prompt

### 8.1 Purpose

The release gate checks whether the candidate is ready to return to the user.

### 8.2 Inputs

- raw user prompt
- current task framing
- final candidate answer
- consensus summary
- release gate mode

### 8.3 Required output schema

```json
{
  "decision": "pass_with_minor_fixes",
  "summary": "The answer is ready after a small caveat is added",
  "minor_fixes_applied": [
    "Added caveat about context dependence"
  ],
  "blocking_issues": [],
  "final_answer_markdown": "Final deliverable answer"
}
```

### 8.4 Prompt intent

The moderator should be instructed to check:

- direct answer quality
- coherence
- plausibility and factual caution
- whether important consensus points are represented
- whether uncertainty is calibrated correctly

If the decision is `fail`, `final_answer_markdown` may still contain the current best candidate, but the blocking issues must explain why another round is required if budget remains.

The release gate must not issue framing updates.

## 9. Repair Prompt

### 9.1 Purpose

The repair prompt is used after a structured internal response fails validation.

### 9.2 Inputs

- schema name
- schema summary or JSON schema
- raw model output
- validation error messages

### 9.3 Required output

The repair prompt must return:

- one valid JSON object
- no markdown fences
- no commentary

### 9.4 Prompt intent

The repair model should be instructed to:

- preserve the original meaning whenever possible
- fix only structural or schema-compliance issues
- not invent new semantic content unless necessary to satisfy required empty arrays or null fields
- use empty arrays or nulls rather than fabricated values when data is missing

## 10. Implementation Guidance

### 10.1 Prompt storage in code

For v1 the prompts should live in code, not external files.

Recommended implementation pattern:

- one module for participant prompts
- one module for moderator prompts
- one module for repair prompts

### 10.2 Provider strategy

If structured output support is available, prefer strict schema mode.

If not available, keep the same logical schema and rely on:

- prompt instructions
- Pydantic validation
- one repair pass

### 10.3 Final answer format

The final answer should remain natural language Markdown or plain text, not a structured JSON object.

## 11. References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [EVENT_SCHEMA.md](./EVENT_SCHEMA.md)
- [RUN_RESULT_SCHEMA.md](./RUN_RESULT_SCHEMA.md)
- OpenRouter Structured Outputs: <https://openrouter.ai/docs/features/structured-outputs>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
