# Streaming UX — Token-by-Token Consensus with Columnar Layout

## Problem

The current implementation uses `agent.run()` (blocking) and DB-polling SSE. After submitting an enquiry, the user sees nothing for ~50 seconds, then all responses appear at once. No visual feedback during LLM generation.

## Solution Overview

Three layers of change:

1. **Backend agents**: Switch from `agent.run()` to `agent.run_stream()` for token-by-token streaming.
2. **SSE transport**: Replace DB-polling with push-based SSE via in-memory `asyncio.Queue` broadcast. DB persistence unchanged (full `LLMCall` on completion).
3. **Frontend**: Columnar layout (one column per model) with cross-section dividers, blinking cursor during streaming, collapsible rounds.

---

## SSE Event Protocol

All model-level events use `llm_model_id` (UUID) as the identifier. The frontend resolves display names from the session's model list.

### New Events

```
event: model_start
data: {"llm_model_id": "uuid", "round_number": 1, "role": "responder"}

event: token_delta
data: {"llm_model_id": "uuid", "round_number": 1, "delta": "The answer"}

event: model_done
data: {"llm_model_id": "uuid", "round_number": 1, "role": "responder",
       "structured": {"confidence": 0.85, "key_points": ["...", "..."]},
       "input_tokens": 150, "output_tokens": 450, "cost": 0.005, "duration_ms": 2100}

event: model_error
data: {"llm_model_id": "uuid", "round_number": 1, "error": "timeout after 60s"}

event: model_catchup
data: {"llm_model_id": "uuid", "round_number": 2, "role": "critic",
       "text_so_far": "All accumulated tokens up to this point..."}

event: phase_change
data: {"from_phase": "responding", "to_phase": "critiquing", "round_number": 2,
       "summary": {"models_completed": 3, "models_failed": 0},
       "model_details": [
         {"llm_model_id": "uuid", "confidence": 0.85, "key_points": ["..."]},
         {"llm_model_id": "uuid", "confidence": 0.9, "key_points": ["..."]}
       ]}

event: round_summary
data: {"round_number": 2, "agreements": ["..."], "disagreements": ["..."], "shifts": ["..."]}
```

### Terminal Events (unchanged)

```
event: consensus_reached
data: {"status": "consensus_reached", "current_round": 3,
       "total_input_tokens": 5000, "total_output_tokens": 12000,
       "total_cost": 0.15, "total_duration_ms": 45000}

event: max_rounds_reached
data: { ... same shape ... }

event: failed
data: { ... same shape ... }
```

### Design Decisions

- `token_delta` is high-frequency, small payloads — just the model ID + text chunk.
- `model_done` carries structured output (confidence, key_points, disagreements) for the cross-section dividers.
- `phase_change` triggers the frontend to render a cross-section divider with aggregated info.
- `round_summary` arrives after `phase_change` (summarizer runs after phase completes) and updates the divider.
- The summarizer agent stays as `agent.run()` (not streamed) since its output goes into the divider, not a column.

---

## Backend Architecture

### In-Memory Broadcast Queue

- `ConsensusOrchestrator` owns a broadcast mechanism for pushing events.
- Module-level `dict[UUID, Broadcast]` maps session IDs to their live broadcasts.
- Orchestrator registers on start, deregisters on completion.
- Multiple SSE clients can connect — each gets its own consumer queue via the broadcast fan-out.

### Why In-Memory (Not Redis)

- Zero infrastructure — no new service in Docker Compose or production.
- Zero latency — same process, no network hop for high-frequency token deltas.
- Works because orchestrator + SSE endpoint live in the same process (single backend worker).
- Clean abstraction boundary: if horizontal scaling is needed later, swap broadcast implementation to Redis pub/sub without changing orchestrator or SSE endpoint.

### Orchestrator Changes

- Switch `agent.run()` to `agent.run_stream()` for responder and critic agents.
- Iterate over the stream, pushing `token_delta` events to the broadcast.
- Accumulate streamed text in memory per model (for `model_catchup` on reconnect).
- On stream completion: extract structured output + usage, push `model_done`, persist full `LLMCall` to DB.
- Push `model_start` before beginning each stream, `phase_change` between rounds.
- Summarizer stays as `agent.run()` — its output goes into the divider via `round_summary` event.

### SSE Endpoint Changes

- On connect: replay completed `llm_calls` from DB as `model_done` events.
- For in-progress models: send `model_catchup` with accumulated text from orchestrator's buffer.
- Then read from broadcast consumer queue and yield events as they arrive. No more 1s polling.
- Keepalive pings remain (15s).
- If session is terminal on connect: replay everything and close.

### Gap Handling

After attaching to the broadcast, do one final DB check for any `llm_calls` created after the replay. If found, send as `model_done` before live streaming begins.

### DB Persistence (Unchanged)

- Full `LLMCall` records written on model completion, same as today.
- Session status transitions same as today.

---

## Frontend Layout

### Columnar Design

- Container: horizontal flexbox, `overflow-x: auto` for horizontal scroll.
- Each column: minimum width ~350px, equal width, fills available space. 2 models = 50/50, 3 = 33/33/33, 4+ = horizontal scroll.
- Column header: model display name + provider icon + status badge.

### Token Streaming

- Text appears incrementally with a blinking cursor (`|`) at the end.
- On completion: cursor disappears, "Done" badge on header, subtle "Waiting for other models..." message at column bottom.
- Markdown rendering: apply only after `model_done`. During streaming, render as plain text to avoid layout jank.

### Cross-Section Dividers

- Full-width bar spanning all columns.
- Content: phase label ("Round 1 -- Initial Responses"), per-model structured data (confidence + key points for Round 1; disagreements for critique rounds), round summary when available.
- Collapsible: click to collapse/expand. Default: previous rounds collapsed, current round expanded.

### Error State

- Column keeps all text rendered so far at reduced opacity (~50%).
- Below the last text: inline alert in the column showing the error message.
- Column stays in place — no removal or resizing.

### Auto-Scroll

Each column scrolls independently to keep the latest text visible.

---

## Replay & Reconnection

1. SSE endpoint replays all completed `llm_calls` from DB as `model_done` events.
2. Frontend renders replayed rounds as collapsed dividers + filled columns. No streaming animation — text appears instantly.
3. For in-progress models: `model_catchup` event delivers accumulated text so far, rendered instantly. Live `token_delta` events continue from that point with cursor.
4. Terminal sessions: replay everything, send terminal event, close.

Nothing is ever lost — completed calls from DB, in-progress text from orchestrator's in-memory buffer.

---

## Testing

### Backend

- **Broadcast**: Events pushed by orchestrator received by multiple consumers. Late-joining consumer gets `model_catchup` for in-progress streams.
- **Streaming orchestrator**: TestModel for LLM calls. Verify event sequence: `model_start` -> `token_delta`(s) -> `model_done` -> `phase_change` -> repeat. Verify `model_error` on failure.
- **SSE endpoint**: Replay from DB for completed sessions. Reconnection mid-session delivers `model_catchup` + live events.
- **Backward compatibility**: Existing orchestrator tests (convergence, max rounds, model failure, heartbeat) pass with streaming refactor.

### Frontend

- **Column layout**: Correct number of columns per session. Horizontal scroll at 4+ models.
- **Token streaming**: `token_delta` appends text. Cursor visible during streaming, gone on `model_done`. "Waiting for other models..." on early completion.
- **Cross-section dividers**: `phase_change` renders divider. Collapsible. `round_summary` updates content.
- **Replay**: Completed sessions render all rounds with collapsed dividers, no animation.
- **Error state**: `model_error` reduces opacity, shows inline alert.

No new infrastructure — TestModel for agents, real Postgres for persistence.
