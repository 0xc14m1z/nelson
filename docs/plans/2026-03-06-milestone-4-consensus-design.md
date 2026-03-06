# Milestone 4 — Core Consensus Engine (with Live UI)

Merges original Milestones 4 and 5. Delivers the full consensus flow
end-to-end: backend orchestrator, SSE streaming, and chat-style frontend.

---

## Database Models

### `sessions`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | UUIDPrimaryKey mixin |
| user_id | UUID FK users (CASCADE) | |
| enquiry | TEXT NOT NULL | |
| status | VARCHAR | `pending`, `responding`, `critiquing`, `consensus_reached`, `max_rounds_reached`, `failed` |
| max_rounds | INT NULL | NULL = until consensus |
| current_round | INT DEFAULT 0 | |
| last_heartbeat_at | TIMESTAMP NULL | Orphan detection |
| total_input_tokens | INT DEFAULT 0 | |
| total_output_tokens | INT DEFAULT 0 | |
| total_cost | NUMERIC DEFAULT 0 | |
| total_duration_ms | INT DEFAULT 0 | |
| created_at | TIMESTAMP | TimestampMixin |
| completed_at | TIMESTAMP NULL | |

### `session_models` (join table)

| Column | Type |
|--------|------|
| session_id | UUID FK sessions (CASCADE) |
| llm_model_id | UUID FK llm_models |
| PK | (session_id, llm_model_id) |

### `llm_calls` (audit trail)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| session_id | UUID FK sessions (CASCADE) | |
| llm_model_id | UUID FK llm_models | |
| round_number | INT | |
| role | VARCHAR | `responder`, `critic`, `summarizer` |
| prompt | TEXT | |
| response | TEXT | |
| input_tokens | INT DEFAULT 0 | |
| output_tokens | INT DEFAULT 0 | |
| cost | NUMERIC DEFAULT 0 | |
| duration_ms | INT DEFAULT 0 | |
| error | TEXT NULL | |
| created_at | TIMESTAMP | |

### `user_settings` change

Add `summarizer_model_id` UUID FK to `llm_models`, nullable.
Defaults to GPT-4o-mini. User can change it in settings.

---

## PydanticAI Agents

Three agents with structured output types.

### Structured types (`agent/types.py`)

```
InitialResponse
    response: str
    confidence: float        (0.0-1.0)
    key_points: list[str]

CritiqueResponse
    has_disagreements: bool   (convergence signal)
    disagreements: list[str]
    revised_response: str

RoundSummary
    agreements: list[str]
    disagreements: list[str]
    shifts: list[str]         (what changed from prior round)
    summary: str              (concise prose)
```

### Agent instances (`agent/consensus_agent.py`)

- **responder_agent**: Takes enquiry, returns `InitialResponse`.
  Runs on each selected model in parallel (round 1 only).

- **critic_agent**: Takes enquiry + round summary + all latest responses,
  returns `CritiqueResponse`. Runs on each selected model in parallel
  (round 2+).

- **summarizer_agent**: Takes a round's full responses, returns
  `RoundSummary`. Runs once per round on the user's configured
  summarizer model (defaults to GPT-4o-mini).

### Prompts (`agent/prompts.py`)

System prompts for each role with template variables:
`{enquiry}`, `{prior_summary}`, `{responses}`.

### Model instantiation

Each agent call uses `model_registry.resolve_model()` to get the API key,
base URL, and slug, then creates a PydanticAI model instance.

---

## ConsensusOrchestrator (`consensus/service.py`)

### Flow

1. Set session status to `responding`, round to 1.
2. **Round 1**: Fan out `responder_agent` to all selected models in
   parallel (`asyncio.gather`). Persist each `llm_call` to DB as it
   completes.
3. **Round 2+**:
   - Run `summarizer_agent` on prior round's responses (single call).
   - Set status to `critiquing`.
   - Fan out `critic_agent` to all models in parallel. Each sees:
     original enquiry + cumulative summary + all latest responses.
   - Persist each `llm_call` to DB.
4. **Convergence check**: All models return
   `has_disagreements == false` -> status `consensus_reached` -> done.
5. **Next round**: Disagreements remain -> increment `current_round`,
   go to step 3.
6. **Hard cap**: 20 rounds -> status `max_rounds_reached` -> done.

### Failure handling

- 60s timeout per LLM call.
- On model failure: log error in `llm_calls` (with `error` field),
  drop model from remaining rounds.
- If <2 models remain -> status `failed`.
- Dropped models emit an SSE event and appear as a system message in
  the chat UI with expandable error details.

### Heartbeat

- Update `last_heartbeat_at` every 10s during execution.
- On app startup: mark sessions stuck in `responding`/`critiquing`
  with heartbeat >5min as `failed`.

### Concurrency

- `asyncio.Semaphore(10)` to cap parallel LLM calls.

### Cost tracking

- Token counts and cost taken directly from PydanticAI's `RunResult`
  (not computed from DB pricing).
- Accumulated into session totals.

### Background execution

- `POST /api/sessions` creates the session, launches the orchestrator
  as a background `asyncio.Task`, returns session ID immediately.

---

## API Endpoints

### Session endpoints (`consensus/router.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sessions` | Create session + launch orchestrator. Body: `{enquiry, model_ids, max_rounds?}`. Validates: min 2 models, user has keys. Returns session ID. |
| GET | `/api/sessions` | List user's sessions, paginated. |
| GET | `/api/sessions/{id}` | Full session + all llm_calls grouped by round. |
| DELETE | `/api/sessions/{id}` | Hard delete with CASCADE. |
| GET | `/api/sessions/{id}/stream` | SSE stream. |

### SSE stream

On connect: replay all existing `llm_calls` as events.
While session is running: poll DB every 1s for new calls
(`created_at > last_seen`).

Event types:
- `status_change` — `{status, round}`
- `response` — round 1 initial response from a model
- `critique` — round 2+ revised response from a model
- `summary` — round summary from summarizer
- `model_dropped` — model failed, includes error details and models remaining
- `round_divider` — marks start of a new round
- `consensus_reached` — terminal event with totals
- `max_rounds_reached` — terminal event with totals
- `error` — session-level failure

Keepalive: 15s SSE comment pings.

---

## Frontend

### Routes

- `/sessions/new` — enquiry form
- `/sessions/[id]` — chat-style session view with SSE
- `/sessions` — session history (sidebar)

### Chat UI (`/sessions/[id]`)

Group chat metaphor where AI models are participants.

- **User message**: The enquiry as the first chat bubble.
- **Model responses**: Color-coded per model. Model name + provider
  icon as the "sender".
- **Round dividers**: System message style — "Round 2 — Critique".
  Subtle, horizontal, centered text.
- **Model dropped**: System message — "Mistral Large dropped —
  timeout after 60s" with expandable error details.
- **Consensus reached**: Highlighted final card/banner showing the
  agreed answer, visually distinct.
- **Max rounds reached**: Similar banner with "no consensus reached"
  note, still shows final responses.

### Model selector (`/sessions/new`)

- Shows models the user has keys for.
- Minimum 2 models required.
- Multi-select grouped by provider.
- Optional max rounds override (default: until consensus).

### SSE client

`sse.js` library for SSE with Authorization header support.

### Data fetching

- TanStack Query for session list and session detail.
- `useConsensusStream` hook using sse.js — connects to SSE endpoint,
  updates local state as events arrive, feeds the chat UI.

### Settings addition

New field on settings page: "Summarizer model" dropdown
(defaults to GPT-4o-mini).

---

## Testing

### Backend

- **Session models**: Create with models, insert llm_calls,
  cascade delete.
- **Agents**: All 3 return correct structured types via `TestModel`.
  Prompts render correctly with variable substitution.
- **ConsensusOrchestrator** (critical test suite):
  - Convergence in N rounds
  - Max rounds hit
  - Model failure + skip
  - Session fails when <2 models remain
  - Cost/token tracking from LLM response
  - Heartbeat updates
- **Session endpoints**: Create, poll until complete, verify
  llm_calls recorded, pagination, delete cascades.
- **Orphan cleanup**: Stuck sessions marked failed on startup.
- **SSE stream**: Event sequence matches expected, replay works
  for completed sessions.

### Frontend

- **Enquiry form**: Renders, validates min 2 models, submits, redirects.
- **Chat UI**: Messages per model with correct colors, round dividers,
  consensus banner.
- **SSE hook**: Processes events correctly, updates state.
- **Session list**: Renders past sessions, empty state.
