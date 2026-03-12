# Nelson Documentation Review and Opus Pre-Plan

## Purpose

This document has two goals:

- summarize whether the current documentation is sufficient to start implementation
- define a pragmatic execution plan for Opus that produces a user-visible slice early

It does not replace the normative specifications. It is a review and sequencing document.

## Current Assessment

The repository is unusually well specified for a project with no implementation yet.

Strong areas already covered:

- product scope and non-goals
- CLI contract and exit codes
- application command/event boundary
- event schema and JSON result schema
- internal prompt contracts
- acceptance-test coverage
- Python engineering and tooling standards

Conclusion:

- implementation can start immediately
- the early contract gaps identified during planning have now been resolved in the normative specs
- the main missing piece is not core architecture, but execution sequencing toward a first visible user outcome

## Resolved Early Decisions

### 1. Clarify final result ownership at the application boundary

This ambiguity has been resolved in the normative specs.

Resolved decision:

- keep events as the canonical runtime protocol
- let the core also produce a typed terminal `RunResult` object for `RunCommand`
- let CLI renderers consume events for progress and use the typed terminal result for `--json` and final human output

This keeps the CLI thin without forcing it to reconstruct large result objects from event replay.

### 2. Define how framing updates are represented after round 1

This ambiguity has been resolved in the normative specs.

Resolved decision:

- add a dedicated `task_framing_updated` event
- keep the event payload as a full framing snapshot rather than a delta

Resolved follow-on rules:

- `RUN_RESULT_SCHEMA` stores only the final effective framing
- the event stream remains the canonical audit trail for framing revisions

### 3. Freeze a live smoke-test model matrix

This was resolved after the initial review.

Resolved decision:

- use `openai/gpt-4.1-mini` and `google/gemini-2.5-flash-lite:nitro` as participants
- use `openai/gpt-4.1` as moderator
- record why they were chosen: cost, availability, structured-output behavior, streaming behavior
- treat that model matrix as test configuration, not as a user-facing default policy

### 4. Add a real onboarding document once scaffolding exists

The repository has planning documents, but no root README or contributor quickstart yet.

That is not a blocker for writing code, but it is the main missing document for humans joining the work.

Recommended minimum future README contents:

- project purpose in 5-10 lines
- required Python and `uv` versions
- bootstrap commands
- canonical lint, type-check, and test commands
- one auth example
- one `nelson run` example

## What Is Not Missing

The following areas are already specific enough to begin implementation without more product writing:

- v1 scope boundaries
- CLI command surface
- output mode behavior
- event envelope and event ordering
- consensus semantics
- release gate modes
- retry and repair expectations
- acceptance-test categories

Opus should not wait for more general planning before starting code.

## Recommended First Visible User Slice

The current milestone set is technically sound, but it is backend-heavy.

To make the project feel real early, the first visible slice should be:

- `nelson auth set`, `auth status`, and `auth clear` working
- `nelson run` working end-to-end for the happy path with:
  - two participants
  - one moderator
  - one prompt source
  - one successful consensus cycle
- all three output modes working:
  - human
  - `--json`
  - `--jsonl`
- at least one real OpenRouter smoke run succeeding with a short prompt

Not required for this first visible slice:

- framing revisions across later rounds
- full retry and repair matrix
- release-gate sophistication beyond the documented happy path
- Logfire integration polish

This gives a real user journey quickly without widening scope.

## Opus Execution Plan

### Phase 0: Spec closeout

Goal:

- resolve the small contract gaps before they create implementation churn

Tasks:

1. Decide terminal result ownership for `RunCommand`.
2. Decide framing-update event semantics.
3. Choose the live smoke-test model matrix.
4. Define the first visible demo checkpoint explicitly.

Exit criteria:

- those decisions are written down before deep implementation starts

### Phase 1: Project scaffold

Goal:

- make the repository runnable and testable immediately

Tasks:

1. Create `pyproject.toml` according to `PYPROJECT_TOOLING_SPEC.md`.
2. Initialize `src/nelson/` and `tests/`.
3. Wire the `nelson` console entrypoint with Typer.
4. Add Ruff, Pyright, pytest, coverage, and pre-commit configuration.

Exit criteria:

- `uv run nelson --help` works
- `uv run nelson auth --help` works
- `uv run nelson run --help` works

### Phase 2: Typed contracts first

Goal:

- lock the system boundaries before runtime behavior expands

Tasks:

1. Implement application command models.
2. Implement event envelope and payload models.
3. Implement run-result models.
4. Implement task-framing, participant-contribution, review, release-gate, and error models.
5. Add JSON Schema export tests.

Exit criteria:

- all schema examples in the docs validate
- JSON Schema export works

### Phase 3: Auth and credential resolution

Goal:

- complete the smallest real user workflow first

Tasks:

1. Implement `auth set`.
2. Implement `auth status`.
3. Implement `auth clear`.
4. Implement credential resolution order for `run`.
5. Add temporary-`HOME` integration tests.

Exit criteria:

- auth acceptance tests pass
- no secret leakage in stdout, stderr, logs, or events

### Phase 4: Provider foundation

Goal:

- unlock real end-to-end runs as early as possible

Tasks:

1. Implement the provider base interface.
2. Implement the OpenRouter adapter in non-streaming mode first.
3. Add streaming support and usage extraction.
4. Map provider failures into typed domain errors.

Exit criteria:

- one real provider invocation succeeds
- streaming deltas can be consumed asynchronously

### Phase 5: Event stream and renderers

Goal:

- make progress and outputs visible before the full consensus engine is complete

Tasks:

1. Implement ordered event emission with stable ids and `sequence`.
2. Implement JSONL renderer.
3. Implement JSON renderer.
4. Implement human renderer with compact progress.

Exit criteria:

- a synthetic run can produce valid human, JSON, and JSONL outputs

### Phase 6: First visible run

Goal:

- deliver the first genuinely useful user-facing experience

Tasks:

1. Implement moderator task framing.
2. Implement participant initial contribution round.
3. Implement moderator candidate synthesis.
4. Implement one successful review-and-close path.
5. Materialize the final `RunResult`.
6. Run one short real OpenRouter demo command.

Exit criteria:

- `nelson run` works end-to-end on the happy path
- final answer is visible in human mode
- `--json` and `--jsonl` are both correct

This is the recommended handoff checkpoint to show progress as a user.

### Phase 7: Consensus hardening

Goal:

- move from a visible demo to a spec-complete core

Tasks:

1. Implement blocking review logic.
2. Implement multi-round continuation.
3. Implement early stop.
4. Implement max-round partial completion.
5. Implement framing revision handling.

Exit criteria:

- consensus acceptance tests pass, including partial-consensus and framing-update paths

### Phase 8: Release gate, repair, and failure policies

Goal:

- complete the resilience rules that make v1 reliable

Tasks:

1. Implement release-gate execution modes.
2. Implement one repair pass for invalid structured output.
3. Implement one retry path where applicable.
4. Implement quorum loss behavior.
5. Implement moderator failure behavior.
6. Add timeout enforcement.

Exit criteria:

- failure and repair acceptance tests pass

### Phase 9: Documentation and release readiness

Goal:

- make the repo usable by the next human or agent without rediscovery

Tasks:

1. Add a root `README.md`.
2. Add quickstart commands.
3. Document the chosen smoke-test model matrix.
4. Document any small implementation decisions taken under spec ambiguity.
5. Run the non-live suite and at least one live smoke test.

Exit criteria:

- repository is understandable without reading every planning document first

## Recommended Task Order for Opus

If Opus wants the shortest path to visible value without breaking the specs, use this order:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 8
10. Phase 9

This is intentionally slightly different from a purely architecture-first path because it pulls the first real user-visible run forward.

## Suggested Demo Checkpoint

The first checkpoint worth showing externally is:

```bash
uv run nelson auth set --api-key <OPENROUTER_KEY>
uv run nelson auth status
uv run nelson run \
  --participant <model-a> \
  --participant <model-b> \
  --moderator <model-c> \
  --prompt "Give me a concise comparison between FastAPI and Django for a new API project." \
  --json
```

Success means:

- auth works
- the run completes without manual intervention
- output matches the documented schema
- the same run can also be observed in human mode and JSONL mode

## Final Recommendation

Do not spend another planning cycle expanding general specs.

Instead:

1. close the few contract gaps above
2. build the scaffold
3. push hard toward the first visible `nelson run`
4. complete the resilience and acceptance matrix afterward

That path preserves the documented architecture while ensuring the project becomes tangible quickly.
