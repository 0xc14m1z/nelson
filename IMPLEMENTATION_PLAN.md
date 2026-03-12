# Nelson v1 Implementation Plan

## Document Status

- Status: Draft approved for implementation handoff
- Intended implementer: Claude
- Scope: Nelson v1 CLI and headless orchestration core
- Current project progress: `Planning complete / Implementation not started`

## Companion Specifications

The following documents refine this implementation plan and should be treated as normative for v1 implementation details:

- [Project Context](./PROJECT_CONTEXT.md)
- [Application Protocol](./docs/APPLICATION_PROTOCOL.md)
- [Coding Agent Handoff](./docs/CODING_AGENT_HANDOFF.md)
- [Python Engineering Standards](./docs/PYTHON_ENGINEERING_STANDARDS.md)
- [Pyproject and Tooling Spec](./docs/PYPROJECT_TOOLING_SPEC.md)
- [CLI Spec](./docs/CLI_SPEC.md)
- [Event Schema](./docs/EVENT_SCHEMA.md)
- [Run Result Schema](./docs/RUN_RESULT_SCHEMA.md)
- [Prompt Spec](./docs/PROMPT_SPEC.md)
- [Acceptance Tests](./docs/ACCEPTANCE_TESTS.md)

## External Reference Sources

The following official sources informed the OpenRouter-specific parts of this plan:

- OpenRouter Authentication: <https://openrouter.ai/docs/api/reference/authentication>
- OpenRouter API Overview: <https://openrouter.ai/docs/api/reference/overview>
- OpenRouter Chat Completions endpoint: <https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request>
- OpenRouter Streaming: <https://openrouter.ai/docs/api/reference/streaming>
- OpenRouter Limits and key metadata: <https://openrouter.ai/docs/api/reference/limits>
- OpenRouter Structured Outputs: <https://openrouter.ai/docs/features/structured-outputs>

## 1. Product Goal

Nelson is a headless orchestration engine with a CLI as its first interface.

The user provides a prompt. Nelson sends that prompt to multiple LLMs, collects their responses, and uses an iterative consensus process to produce a final answer that is more complete and more accurate than a single-model answer.

The core goal is not simple voting. The goal is to combine complementary strengths across models so that the final answer:

- covers multiple relevant facets of the problem
- removes weak or incorrect parts
- converges toward the best answer available within the configured model set

The first interface is a CLI because:

- it is easy to automate
- it is easy to use from Codex, Claude, and shell pipelines
- the future UI can be built on top of the same headless core and event stream

## 2. Product Principles

- CLI first, but core must be UI-ready.
- The orchestration engine must be headless and event-driven.
- All adapters must communicate with the core through a typed command/event boundary.
- All internal reasoning phases must be strongly typed.
- The final user-facing answer remains natural language.
- OpenRouter is the only provider implemented in v1.
- The provider layer should still be kept provider-agnostic.
- The system must be async from day one.
- The system must support streaming as an event stream, not only as plain text.
- The v1 runtime is one-shot only.

## 3. Scope for v1

### Included

- Python implementation
- `uv` as the main Python workflow
- CLI with `auth` and `run`
- async orchestration core
- OpenRouter provider implementation
- one-shot prompt execution
- multiple participant models
- one moderator model
- iterative consensus
- release gate before final answer
- output modes: human, `--json`, `--jsonl`
- strongly typed event stream
- internal system prompts embedded in code
- API key storage in `~/.nelson/`
- validation, retry, timeout, and repair behavior

### Explicitly out of scope for v1

- multi-turn conversations
- persistent run history
- `inspect` command
- project-local `.nelson/`
- external prompt files for system prompts
- profiles
- exposed generation params like `temperature`
- attachments or extra context files beyond the main prompt file
- keychain integration
- multiple providers beyond OpenRouter

## 4. Main User Flows

### 4.1 Authenticate once

The user stores the OpenRouter API key:

```bash
nelson auth set --api-key <OPENROUTER_KEY>
```

The user checks whether the key exists and whether it works:

```bash
nelson auth status
```

The user clears the saved key:

```bash
nelson auth clear
```

### 4.2 Run with direct prompt

```bash
nelson run \
  --participant openai/gpt-4.1 \
  --participant anthropic/claude-3.7-sonnet \
  --moderator openai/gpt-4.1 \
  --prompt "What are the main principles for building a Python application?" \
  --max-rounds 10
```

### 4.3 Run from file

```bash
nelson run \
  --participant openai/gpt-4.1 \
  --participant anthropic/claude-3.7-sonnet \
  --moderator openai/gpt-4.1 \
  --prompt-file ./prompt.md
```

### 4.4 Run from stdin

```bash
cat prompt.md | nelson run \
  --participant openai/gpt-4.1 \
  --participant anthropic/claude-3.7-sonnet \
  --moderator openai/gpt-4.1 \
  --stdin
```

### 4.5 Structured output for agents and UI

```bash
nelson run ... --json
nelson run ... --jsonl
```

## 5. CLI Contract

### 5.1 Commands

- `nelson auth set --api-key <KEY>`
- `nelson auth status`
- `nelson auth clear`
- `nelson run ...`

### 5.2 `run` flags required in v1

- `--participant <model>` repeatable, minimum 2
- `--moderator <model>` required
- exactly one of:
  - `--prompt <text>`
  - `--prompt-file <path>`
  - `--stdin`

### 5.3 `run` flags optional in v1

- `--max-rounds <int>` default `10`
- `--openrouter-api-key <key>` explicit per-run override
- `--release-gate <mode>` where mode is expected to support:
  - `off`
  - `auto`
  - `on`
- `--json`
- `--jsonl`

### 5.4 Input source rules

- Exactly one input source is allowed.
- If more than one source is provided, Nelson must return an explicit error.
- No hidden precedence between `--prompt`, `--prompt-file`, and `--stdin`.

### 5.5 Credentials resolution order

1. `--openrouter-api-key`
2. `OPENROUTER_API_KEY`
3. saved key from `~/.nelson/`

### 5.6 Human-readable output behavior

Human mode is the default.

It should show:

- high-level progress
- phase and round changes
- final answer
- consensus status always
- if consensus is partial, the reasons must be shown
- if `minor_revise` suggestions were incorporated, those should be shown briefly

It should not show:

- model identities by default
- raw event payloads
- full internal task framing

### 5.7 JSON output behavior

`--json` returns a single structured final result.

It should include:

- final answer
- consensus status
- consensus details
- participant and moderator model identities
- round count
- release gate result
- any residual disagreement
- usage if available

### 5.8 JSONL output behavior

`--jsonl` streams one JSON object per line for the full run.

It is the canonical machine-readable event stream for:

- automation
- future UI
- Codex / Claude integration

## 6. Consensus Strategy v1

### 6.1 High-level intent

The consensus strategy is designed to combine different model perspectives into a better answer, not merely select a winner.

The system should converge by synthesis plus objection handling.

### 6.2 Roles

#### Participant

Each participant:

- receives the user prompt
- receives the moderator's task framing
- can challenge the framing
- proposes an initial answer
- provides limits and assumptions
- reviews the moderator's candidate answer in later rounds

#### Moderator

The moderator:

- performs task framing at the start
- synthesizes participant outputs into a candidate answer
- selects relevant excerpts to show in subsequent rounds
- decides whether framing updates are required
- classifies whether revisions are minor or substantial
- performs the final release gate
- may stop early if consensus is sufficient

The moderator is configured separately through the CLI. It is a distinct role. It may use the same model id as a participant, but that is not required.

### 6.3 Task framing

Task framing is always active in v1.

It is performed by the moderator before participant generation starts.

Task framing must produce a structured output that includes at least:

- task type
- sensitivity level
- quality criteria
- likely important aspects to cover
- ambiguities or assumptions

Task framing is:

- always used internally
- visible only via `--json`, `--jsonl`, or debug-oriented tooling in the future
- challengeable by participants

If participants raise substantial issues with the framing, the moderator may update it formally for later rounds.

Minor comments on framing do not require a formal framing update.

Resolved v1 rules:

- framing updates are for material changes only
- framing updates may occur in any consensus round
- framing updates must be emitted as a dedicated `task_framing_updated` event
- the event belongs to the current round, but the new framing becomes effective only from the next round
- a material framing update invalidates the current candidate immediately
- an invalidated candidate must not enter review and must not emit consensus events
- the next round must collect fresh contributions from all active participants under the new framing version
- contributions produced under earlier framing versions remain historical only and must not be reused as substantive round inputs after a material reframing
- if a material framing update occurs with no remaining round budget, the run fails with `framing_update_budget_exhausted`

Rationale:

- a material reframing means the current candidate was built on the wrong task interpretation
- a dedicated event keeps reframing distinct from both synthesis and review semantics
- restarting all active participants under one shared framing version keeps the protocol easier to reason about and test

### 6.4 Participant contribution rounds

In the first contribution round, each participant returns a structured object containing:

- proposed answer
- limits and assumptions
- comments on task framing, if any

If a later round begins because of a material framing update:

- every active participant must contribute again under the new framing version
- that regenerated contribution is a fresh reframed contribution, not a continuation of the obsolete candidate path

### 6.5 Candidate synthesis

After receiving the initial participant outputs, the moderator produces a candidate answer.

This candidate should:

- combine complementary insights
- remove obvious redundancy
- preserve useful nuance
- resolve conflicts where possible
- surface uncertainty when certainty is not justified

### 6.6 Review states

When participants review a moderator candidate, they must emit exactly one of:

- `approve`
- `minor_revise`
- `major_revise`
- `reject`

Meaning:

- `approve`: candidate is ready
- `minor_revise`: candidate is basically ready but would benefit from small improvements
- `major_revise`: there is a substantial issue that blocks completion
- `reject`: the candidate is materially wrong, misaligned, or unusable

### 6.7 Blocking rules

Consensus may close only when there are:

- no `major_revise`
- no `reject`

`minor_revise` does not block closure.

The moderator may still choose to integrate `minor_revise` feedback before closing if it improves the answer meaningfully.

### 6.8 Review context in later rounds

In later rounds, a participant should not receive all raw outputs from all other models.

Instead, the participant receives:

- the current moderator candidate
- a moderator-written synthesis of important points
- selected relevant excerpts from other participant outputs

Those excerpts are selected by the moderator.

Review is anonymized:

- participants do not see which model produced which excerpt
- Nelson keeps internal model attribution
- model attribution appears only in structured output and future inspect/debug tooling

### 6.9 Early stop

The moderator may stop before `max_rounds` if consensus is sufficient according to the blocking rules.

### 6.10 Max rounds fallback

If Nelson reaches `max_rounds` without full consensus:

- it still returns the last moderator candidate
- it marks the result as not fully consensual
- it includes the substantive remaining disagreements

Residual disagreement should be visible:

- always in human-readable output when consensus is partial
- always in `--json` and `--jsonl`

### 6.11 Release gate

The release gate is a final quality-control step performed by the moderator after candidate consensus appears sufficient.

It is not a full extra debate round. It is a delivery readiness check.

The release gate should verify:

- prompt adherence
- coherence and internal consistency
- factual or technical plausibility
- whether important aspects surfaced during consensus are covered
- whether uncertainty is communicated properly
- whether the final wording is clear and not unnecessarily redundant

The release gate mode must support:

- `off`
- `auto`
- `on`

Default behavior in v1 should be `auto`.

In `auto`, the moderator uses the task classification and sensitivity assessment to decide whether the release gate is needed.

The release gate produces a structured result such as:

- `pass`
- `pass_with_minor_fixes`
- `fail`

If `pass_with_minor_fixes`, the moderator may apply the minor fixes directly.

If `fail`, Nelson should continue with another round if the round budget allows.

If rounds are exhausted, Nelson returns the best candidate available and marks the result accordingly.

The release gate must not issue a framing update.

If the release gate discovers a framing-level problem:

- it should fail the release gate
- the run may return to a normal consensus round if budget remains
- reframing itself still belongs to the consensus loop, not the release gate

## 7. Runtime Failure and Recovery Rules

### 7.1 Participant failure

If a participant call fails due to timeout, provider error, or invalid structured output:

- Nelson should attempt one network retry if applicable
- Nelson should attempt one structured-output repair if parsing fails

If the participant is still unusable after that, the run may continue only if at least two valid participants remain.

If fewer than two valid participants remain, the run fails.

Resolved v1 rules:

- a participant that remains unusable after bounded retry and repair is permanently excluded for the rest of the run
- permanent exclusion should be emitted explicitly as `participant_excluded`
- if quorum remains valid, the current round continues rather than restarting
- if exclusion happens during review and quorum remains valid, the round may still close on the basis of the remaining reviewers
- if exclusion drops the active set below quorum, the run fails immediately and the interrupted round does not emit `round_completed`

Historical outputs from an excluded participant may remain available as passive historical context.

However, after a later material framing update, contributions produced under the obsolete framing version must no longer be reused as substantive round inputs.

### 7.2 Moderator failure

If the moderator fails:

- Nelson should attempt one retry or repair as appropriate
- if the moderator still fails, the run fails

There is no automatic moderator fallback in v1.

### 7.3 Timeout

- Default timeout per model call: `60s`

### 7.4 Structured output repair

Internal phases use typed structured outputs.

If a model returns invalid or incomplete structured data:

- Nelson should run one repair step
- repair should be explicit and scoped to schema compliance
- if repair fails, the call is considered failed

## 8. Storage Layout

### 8.1 Global directory

All v1 storage is user-global only:

```text
~/.nelson/
```

### 8.2 Saved credential

Recommended v1 layout:

```text
~/.nelson/openrouter_api_key
```

Requirements:

- create `~/.nelson/` if missing
- apply restrictive permissions to the key file
- never print the full key in CLI output

### 8.3 No persistent run storage in v1

Do not save:

- transcripts
- event logs
- run metadata
- inspectable history

Those belong to future work.

## 9. Internal Prompting Strategy

In v1, system prompts are internal to the codebase.

There should be at least two distinct system prompts:

- participant system prompt
- moderator system prompt

Internal prompts should be written so that:

- all internal workflow steps return structured typed output
- the moderator behaves as orchestrator and synthesizer, not as sole authority
- participants challenge framing when necessary
- participants distinguish between minor and major problems

The final answer generation step may return natural language instead of structured JSON.

External prompt files are intentionally deferred to future work.

## 10. Python Architecture

### 10.1 Implementation style

- Python
- async-first runtime
- `uv` for project and environment workflow
- `Typer` for CLI
- `httpx` for async HTTP and streaming
- `pydantic` for typed models and schema export

Optional but likely useful:

- `rich` for human-readable progress and terminal rendering

### 10.2 Proposed package layout

```text
src/nelson/
  __init__.py
  main.py
  cli/
    __init__.py
    app.py
    auth.py
    run.py
    render_human.py
    render_json.py
    render_jsonl.py
  core/
    __init__.py
    dispatcher.py
    engine.py
    session.py
    progress.py
    errors.py
  consensus/
    __init__.py
    orchestrator.py
    task_framing.py
    synthesis.py
    review.py
    release_gate.py
    stopping.py
  providers/
    __init__.py
    base.py
    openrouter.py
  prompts/
    __init__.py
    participant.py
    moderator.py
    repair.py
  protocols/
    __init__.py
    application.py
    events.py
    framing.py
    responses.py
    review.py
    release_gate.py
    run_result.py
  storage/
    __init__.py
    auth.py
  utils/
    __init__.py
    clock.py
    ids.py
    json.py
```

This exact layout can be adjusted, but the separation of concerns should remain.

### 10.3 Core boundaries

The CLI should not contain orchestration logic.

The adapter-to-core boundary must follow the application protocol:

- adapters submit typed commands
- the core processes them
- the core emits typed events
- adapters render or consume those events

The implementation should treat this boundary as a local in-process bus in v1.

The core should:

- accept typed application commands
- resolve runtime configuration
- run the orchestration loop
- emit typed events
- produce a final typed result

The recommended implementation shape is a command execution object exposing:

- an ordered event stream
- a typed terminal result when the command reaches completion

For `RunCommand`, that terminal result should be the canonical `RunResult` object used by `--json`.

Rationale:

- events remain the canonical runtime contract for streaming observers
- a terminal result keeps JSON and human renderers thin and avoids adapter-side reconstruction of large result objects

The CLI should:

- parse command arguments
- resolve interface-local concerns such as prompt text collection
- construct typed application commands
- invoke the core through the application protocol
- render events or final results according to output mode

### 10.4 Provider abstraction

The provider abstraction should stay small.

At minimum it must support:

- standard request execution
- streaming token deltas
- usage reporting when available
- timeout and retry hooks

Only OpenRouter needs to be implemented in v1, but the abstraction should not hardcode provider-specific assumptions into the orchestration engine.

## 11. Event Protocol

### 11.1 Design goal

The event stream is a core product contract, not just a debugging aid.

It must be reusable by:

- CLI human renderer
- CLI JSONL mode
- future UI
- future agent integrations

### 11.2 Event envelope

Every event should contain at least:

- `event_id`
- `command_id`
- `run_id`
- `timestamp`
- `sequence`
- `type`
- `round`
- `phase`
- `role`
- `model`
- `payload`

Notes:

- `sequence` should provide total ordering for the emitted stream
- `command_id` identifies the application command that produced the event stream
- `round` may be `null` for non-round events such as startup
- `role` may be `participant`, `moderator`, or `system`
- `model` may be `null` for system-level events

### 11.3 Event typing

All events must be strongly typed through `Pydantic` models.

The codebase should be able to export JSON Schema for the event protocol.

### 11.4 Minimum event families for v1

System lifecycle:

- `run_started`
- `run_completed`
- `run_failed`

Progress:

- `progress_updated`

Consensus lifecycle:

- `consensus_pending`
- `consensus_reached`
- `consensus_partial`

Task framing:

- `task_framing_started`
- `task_framing_completed`
- `task_framing_updated`

Model execution:

- `model_started`
- `model_delta`
- `model_completed`
- `model_failed`
- `participant_excluded`

Round lifecycle:

- `round_started`
- `round_completed`

Candidate lifecycle:

- `candidate_created`
- `candidate_updated`

Review lifecycle:

- `review_started`
- `review_completed`

Release gate:

- `release_gate_started`
- `release_gate_completed`

Usage:

- `usage_reported`

This list can evolve, but v1 should start with explicit domain events rather than overloaded generic events.

## 12. Progress Indicator Model

### 12.1 Why it matters

The progress indicator is required for three reasons:

- the human CLI should feel alive and legible
- future UIs need stable progress semantics
- long multi-model orchestration runs need observable state transitions

### 12.2 Constraint

True total completion percentage is not fully deterministic because:

- participant calls run in parallel
- token generation speed varies
- the number of completed rounds can stop early
- release gate may or may not run depending on `auto`

Therefore, Nelson should expose both:

- stage-aware progress
- an estimated overall progress percentage

### 12.3 Proposed progress payload

Each `progress_updated` event should include a typed payload with fields such as:

- `phase_name`
- `phase_index`
- `phase_count_estimate`
- `round`
- `max_rounds`
- `completed_units`
- `total_units`
- `stage_progress`
- `overall_progress_estimate`
- `is_estimate`
- `message`

Recommended meaning:

- `phase_name`: current high-level phase
- `phase_index`: ordinal index of the current phase
- `phase_count_estimate`: total expected number of phases based on current plan
- `completed_units`: completed work units within the current phase
- `total_units`: total work units expected in the current phase
- `stage_progress`: value between `0.0` and `1.0` for the current phase
- `overall_progress_estimate`: value between `0.0` and `1.0` for the whole run
- `is_estimate`: always `true` for the overall value in v1

### 12.4 Phase model

Recommended high-level phases:

1. startup
2. task_framing
3. participant_generation_round_1
4. synthesis_round_n
5. review_round_n
6. release_gate
7. finalization

### 12.5 Work units

Suggested unit semantics:

- in participant generation, one unit per participant completion
- in review, one unit per participant review completion
- in synthesis, one unit for moderator completion
- in release gate, one unit for moderator completion

### 12.6 Human-readable rendering

The human renderer should show compact progress such as:

```text
Round 2/10 · review · 1/3 complete · est. 34%
```

The human output should remain stable and short.

### 12.7 Progress weighting

The implementation should avoid pretending that progress is exact.

Recommended weighting approach:

- startup: 5%
- task framing: 10%
- participant generation: 20%
- each active consensus round: distributed across the remaining budget
- release gate: 10%
- finalization: 5%

Important:

- `overall_progress_estimate` is heuristic
- if consensus is reached early, the progress may jump forward sharply
- that is acceptable as long as the event explicitly marks the value as an estimate

### 12.8 Alternative safeguard

If the heuristic percentage feels misleading during implementation, Claude may ship:

- a textual phase-and-unit progress indicator as the primary signal
- a numeric estimated percentage as secondary metadata

That fallback is acceptable and still consistent with this plan.

## 13. Typed Internal Schemas

At minimum, v1 should define typed models for:

- task framing result
- participant initial contribution
- review result
- release gate result
- minimal auth command results
- usage snapshot
- final run result
- every event payload

These models should be strict enough to keep internal phases machine-readable and easy to validate.

They should also make the following runtime facts explicit:

- the final effective framing version
- whether any participant was excluded
- whether aggregate usage is complete or only partially known

## 14. Suggested Implementation Milestones for Claude

The milestones below are sequenced to keep the implementation incremental and testable.

### Milestone 1: Repository scaffold and packaging

Deliverables:

- `uv` project initialized
- package layout created
- `Typer` CLI entrypoint wired
- basic `nelson auth` and `nelson run` command skeletons

Exit criteria:

- `uv run nelson --help` works
- `uv run nelson auth --help` works
- `uv run nelson run --help` works

Suggested progress marker:

- Project progress: `10%`

### Milestone 2: Auth storage and credential resolution

Deliverables:

- create `~/.nelson/` if missing
- implement `auth set`
- implement `auth status`
- implement `auth clear`
- implement credential resolution order for `run`

Exit criteria:

- saved key can be written and removed
- `auth status` distinguishes missing, present, and invalid key states
- CLI never leaks the full secret

Suggested progress marker:

- Project progress: `20%`

### Milestone 3: Provider abstraction and OpenRouter adapter

Deliverables:

- provider base interface
- OpenRouter implementation
- non-streaming request support
- streaming support
- timeout handling
- usage extraction where available

Exit criteria:

- a single prompt can be sent successfully through OpenRouter
- streaming deltas can be consumed asynchronously

Suggested progress marker:

- Project progress: `35%`

### Milestone 4: Event protocol and renderer foundations

Deliverables:

- typed event envelope
- core event types
- JSON renderer
- JSONL renderer
- human renderer skeleton
- sequence ordering logic

Exit criteria:

- `run` can emit a syntactically valid event stream
- JSON Schema export is possible for the event models

Suggested progress marker:

- Project progress: `50%`

### Milestone 5: Consensus engine core

Deliverables:

- task framing by moderator
- participant initial round
- moderator candidate synthesis
- participant review states
- blocking rules
- early stop
- max rounds handling

Exit criteria:

- a full multi-model roundtrip works end to end
- consensus and partial consensus states are both representable

Suggested progress marker:

- Project progress: `70%`

### Milestone 6: Release gate, retry, repair, and failures

Deliverables:

- release gate flow
- repair logic for invalid structured outputs
- retry logic
- quorum handling
- moderator failure path

Exit criteria:

- invalid internal JSON outputs can trigger repair
- participant loss behaves according to quorum rules
- moderator failure aborts correctly

Suggested progress marker:

- Project progress: `85%`

### Milestone 7: Human UX and output polish

Deliverables:

- compact progress rendering
- final answer formatting
- partial consensus explanation
- brief rendering of incorporated minor revisions

Exit criteria:

- human mode is readable during long runs
- user can distinguish full vs partial consensus

Suggested progress marker:

- Project progress: `95%`

### Milestone 8: Validation and release readiness

Deliverables:

- integration checks
- basic fixtures or tests for typed schemas and CLI validation
- smoke tests for auth and run
- documentation updates

Exit criteria:

- core flows execute reliably
- structured outputs validate
- CLI contract matches this plan

Suggested progress marker:

- Project progress: `100%`

## 15. Resolved Design Decisions

The following design decisions were resolved after the initial handoff draft and should now be treated as normative for v1.

- Application protocol: one dispatched command yields a command execution with an event stream plus a terminal typed result. Why: events remain the canonical runtime protocol, while `RunResult` avoids adapter-side reconstruction for `--json`.
- Auth terminal results: `auth` commands also resolve to minimal typed results, documented inside the application protocol rather than in a separate schema document. Why: future adapters and tests benefit from typed terminal state, but `auth` does not justify a separate public JSON contract in v1.
- Reframing: use a dedicated `task_framing_updated` event with a full framing snapshot. Why: a dedicated event keeps initial framing and later reframing semantically distinct and easier to replay.
- Reframing scope: only material framing changes justify reframing. Why: minor wording edits are not worth invalidating candidates and restarting contribution rounds.
- Reframing timing: reframing may happen in any consensus round but never in the release gate. Why: framing is part of the consensus loop, while the release gate is a final delivery check.
- Candidate invalidation: a material reframing invalidates the current candidate immediately and skips review and consensus for that candidate. Why: a candidate built on the wrong framing should not advance as though it were still reviewable.
- Participant regeneration after reframing: all active participants regenerate fresh contributions under the new framing. Why: mixing outputs from different framing versions creates ambiguous semantics.
- Round accounting: rounds invalidated by reframing still count toward `rounds_completed`. Why: real work was performed and the round budget should reflect that cost.
- Budget exhaustion after reframing: if no round remains to execute the new framing, the run fails with `framing_update_budget_exhausted`. Why: returning a candidate built under an invalidated framing would be semantically weak.
- Participant exclusion: participants are permanently excluded after bounded retry and repair fail. Why: a stable active set is simpler and more deterministic than allowing re-entry.
- Exclusion semantics: the current round continues if quorum remains, including during review. Why: valid work from remaining participants should not be discarded unnecessarily.
- Event protocol for exclusion: use a dedicated `participant_excluded` event immediately after the causal failure chain. Why: invocation failure and active-set mutation are distinct runtime facts.
- Usage accounting: totals include all known usage from retries, repairs, failures, and later-excluded participants, and expose completeness explicitly. Why: cost reporting should reflect the real run, while still admitting incomplete provider metadata.
- Live smoke matrix: participants `openai/gpt-4.1-mini` and `google/gemini-2.5-flash-lite:nitro`, moderator `openai/gpt-4.1`. Why: lower-cost participants plus a stronger moderator provide a practical v1 smoke-test balance while staying aligned with documented OpenRouter structured-output support.

## 16. Open Questions Still Worth Resolving Before or During Implementation

These are not blockers for scaffolding, but they should be resolved before Nelson is considered stable.

- Whether usage should remain provider-reported only in v1, or whether Nelson should later query generation stats for more exact cost metadata
- Whether human mode should later gain a quieter pipe-friendly variant in addition to the default progress output

## 17. Future Work

The following items are intentionally deferred:

- multi-turn session memory
- persistent run storage
- `inspect` command
- project-local `.nelson/`
- profiles
- external prompt files
- keychain-backed secret storage
- project and user config files
- exposed generation parameters
- additional providers
- attachments and external context documents
- richer debug and replay tooling
- UI layer built on the event stream

## 18. Final Implementation Guidance for Claude

Implementation should optimize for clean boundaries over premature feature breadth.

The most important architectural decisions to preserve are:

- headless async core
- typed event stream
- moderator-driven synthesis
- anonymized participant review
- one-shot v1 scope
- provider abstraction with only OpenRouter implemented

If tradeoffs are needed during implementation, prefer:

- preserving the event protocol
- preserving the consensus semantics
- preserving strong typing

over:

- adding convenience features early
- adding storage or configuration complexity
- widening the v1 scope
