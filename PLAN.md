# Nelson — Consensus Agent Implementation Plan

## Context

Build a multi-LLM consensus system from scratch. A user submits an enquiry, the system fans it out to multiple LLMs, collects responses, then iterates critique rounds until the models converge on a consensus. The user picks their preferred final answer from all revised responses.

**Tech stack**: Next.js (frontend) + FastAPI (backend) + PydanticAI (agents) + PostgreSQL + Pydantic Logfire (observability)

**Infra**: Docker Compose locally, DigitalOcean App Platform + Managed Postgres in prod.

---

## Key Decisions

| Area | Decision |
|------|----------|
| **Deployment** | DigitalOcean App Platform (backend + frontend) + Managed Postgres. No Caddy/nginx needed. |
| **Makefile** | Yes — convenience wrapper for common dev commands |
| **CI/CD** | GitHub Actions from Phase 1 (lint + test). App Platform auto-deploys from GitHub. |
| **Seed data** | Big 4 + OpenRouter: OpenAI, Anthropic, Google, Mistral, OpenRouter |
| **Cost storage** | DECIMAL (sub-cent, stored as dollars e.g. 0.0042) |
| **Session delete** | Hard delete with CASCADE |
| **JWT expiry** | 15min access token + 7d refresh token |
| **Email provider** | Mailpit (local dev/test via SMTP), Resend (production only) |
| **Rate limiting** | 3 magic link requests per email per 15min (DB check) |
| **Key validation** | Validate on save by calling provider API |
| **Encryption** | Single FERNET_KEY in .env (managed via App Platform env vars) |
| **Consensus flow** | Iterative convergence — no synthesizer role (see below) |
| **Convergence** | Structured `has_disagreements: bool` — consensus when all models return false |
| **Critique prompt** | Original enquiry + GPT-4o-mini summary of prior rounds + latest round's full responses |
| **Round summaries** | GPT-4o-mini generates a summary after each round (tracked as `summarizer` role in llm_calls) |
| **Default mode** | "Until consensus" — iterate until models agree |
| **Round override** | User can set specific round count in settings or per enquiry |
| **Hard cap** | 20 rounds max (present results with "no consensus reached" note) |
| **Critique format** | All responses at once per model (N calls per round, not N*(N-1)) |
| **Model count** | Minimum 2, no maximum (user decides) |
| **Failure handling** | Skip failed model, continue if ≥2 models remain |
| **Orphaned sessions** | Heartbeat every 10s + startup cleanup (fail sessions stale >5min) |
| **OpenRouter** | Dual role: provider (own models) + fallback route (proxy via slug translation e.g. `gpt-4o` → `openai/gpt-4o`) |
| **Pay-per-use** | Phase 6 — Stripe metered billing, single platform OpenRouter key, $20/mo default cap (user-adjustable). Phases 1-5 own-keys + OpenRouter only. |
| **LLM timeout** | 60 seconds per call |
| **Final output** | All revised answers side by side, user picks preferred |
| **SSE replay** | From database (query llm_calls), no in-memory buffers |
| **Live events** | DB polling every 1s (avoids PgBouncer/NOTIFY issues with managed Postgres) |
| **SSE keepalive** | 15s comment pings (App Platform idle timeout) |
| **SSE client** | `@microsoft/fetch-event-source` (supports Authorization header, unlike native EventSource) |
| **Dark mode** | Day one (Mantine native support) |
| **Data fetching** | TanStack Query |
| **Layout** | Desktop-first, responsive |

---

## Project Structure

```
nelson/
├── docker-compose.yml          # Postgres + backend + frontend (local dev)
├── .env.example
├── Makefile
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   └── app/
│       ├── main.py              # FastAPI app, CORS, Logfire setup
│       ├── config.py            # Pydantic Settings (env-based)
│       ├── database.py          # SQLAlchemy async engine + session
│       ├── auth/
│       │   ├── router.py        # /auth/magic-link, /auth/verify, /auth/refresh
│       │   ├── service.py       # Token gen, verification, email (SMTP/Resend)
│       │   ├── dependencies.py  # get_current_user
│       │   └── schemas.py
│       ├── users/
│       │   ├── router.py        # GET/PUT /users/me, /users/me/settings
│       │   ├── service.py
│       │   └── schemas.py
│       ├── keys/
│       │   ├── router.py        # CRUD /keys
│       │   ├── service.py       # Store, validate, retrieve keys
│       │   ├── encryption.py    # Fernet encrypt/decrypt
│       │   └── schemas.py
│       ├── agent/
│       │   ├── consensus_agent.py  # 3 PydanticAI agents (responder, critic/reviser, summarizer)
│       │   ├── prompts.py          # System prompts per role
│       │   ├── model_registry.py   # Resolve model → PydanticAI model instance
│       │   └── types.py            # Structured output types
│       ├── consensus/
│       │   ├── router.py        # POST/GET /sessions, SSE /sessions/{id}/stream
│       │   ├── service.py       # ConsensusOrchestrator (iterative convergence)
│       │   └── pricing.py       # Cost calc from token counts
│       ├── billing/
│       │   ├── router.py
│       │   └── service.py
│       └── models/              # SQLAlchemy ORM
│           ├── user.py
│           ├── provider.py      # providers table
│           ├── llm_model.py     # models table
│           ├── api_key.py
│           ├── session.py
│           └── llm_call.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── app/
        │   ├── login/page.tsx
        │   ├── login/verify/page.tsx
        │   ├── dashboard/page.tsx
        │   ├── enquiry/page.tsx
        │   ├── sessions/[id]/page.tsx
        │   ├── settings/page.tsx
        │   └── usage/page.tsx
        ├── components/
        │   ├── consensus/
        │   │   ├── ModelSelector.tsx
        │   │   ├── ConsensusProgress.tsx    # SSE-driven live progress
        │   │   ├── ResponseCard.tsx
        │   │   ├── CritiqueCard.tsx
        │   │   └── SessionTimeline.tsx
        │   └── settings/
        │       ├── ApiKeyForm.tsx
        │       └── DefaultModelsForm.tsx
        ├── lib/
        │   ├── api.ts              # Fetch wrapper with JWT
        │   └── sse.ts              # useConsensusStream hook (@microsoft/fetch-event-source)
        └── types/index.ts
```

---

## Database Schema

### providers (data-driven, not hardcoded enum)
`id` UUID PK | `slug` VARCHAR UNIQUE (e.g. `openai`, `anthropic`, `google`, `mistral`, `openrouter`) | `display_name` | `base_url` VARCHAR | `is_active` BOOL | `created_at`

Seeded on first migration with known providers. New providers added via migration or admin, no code changes needed.

### llm_models (data-driven model catalog)
`id` UUID PK | `provider_id` FK providers | `slug` VARCHAR (e.g. `gpt-4o`, `claude-sonnet-4-20250514`) | `display_name` | `input_price_per_mtok` DECIMAL | `output_price_per_mtok` DECIMAL | `is_active` BOOL | `context_window` INT | `created_at`

UNIQUE(`provider_id`, `slug`). Pricing lives in the DB, easy to update.

### users
`id` UUID PK | `email` VARCHAR UNIQUE | `display_name` | `billing_mode` VARCHAR (`own_keys`, `openrouter`) — `pay_per_use` added in Phase 6 | `created_at` | `updated_at`

### user_settings
`user_id` FK users PK | `max_rounds` INT NULL (NULL = "until consensus") | `created_at` | `updated_at`

### user_default_models (join table)
`user_id` FK users | `llm_model_id` FK llm_models | PRIMARY KEY(`user_id`, `llm_model_id`)

### magic_links
`id` UUID PK | `email` | `token_hash` VARCHAR | `expires_at` (+15min) | `used_at` | `created_at`

### refresh_tokens
`id` UUID PK | `user_id` FK | `token_hash` | `expires_at` | `revoked_at` | `created_at`

### api_keys
`id` UUID PK | `user_id` FK | `provider_id` FK providers | `encrypted_key` BYTEA (Fernet) | `is_valid` BOOL | `validated_at` | `created_at`

UNIQUE(`user_id`, `provider_id`)

### sessions
`id` UUID PK | `user_id` FK | `enquiry` TEXT NOT NULL | `status` VARCHAR (`pending`, `responding`, `critiquing`, `consensus_reached`, `max_rounds_reached`, `failed`) | `max_rounds` INT NULL (NULL = until consensus, override from user settings) | `current_round` INT DEFAULT 0 | `last_heartbeat_at` TIMESTAMP NULL | `total_input_tokens` INT | `total_output_tokens` INT | `total_cost` DECIMAL | `total_duration_ms` INT | `created_at` | `completed_at`

### session_models (which models were selected for this session)
`session_id` FK sessions | `llm_model_id` FK llm_models | PRIMARY KEY(`session_id`, `llm_model_id`)

### llm_calls (every single exchange, the audit trail)
`id` UUID PK | `session_id` FK | `llm_model_id` FK llm_models | `round_number` INT | `role` VARCHAR (`responder`, `critic`, `summarizer`) | `prompt` TEXT | `response` TEXT | `input_tokens` INT | `output_tokens` INT | `cost` DECIMAL | `duration_ms` INT | `error` TEXT NULL | `created_at`

---

## Consensus Flow (Core Architecture)

Three PydanticAI agents with structured output types — iterative convergence, no synthesizer:

1. **Round 1 — Initial Response** (parallel): Each selected model answers the enquiry independently
   → `InitialResponse(response: str, confidence: float, key_points: list[str])`

2. **Round 2+ — Critique & Revise** (parallel, iterates): Each model receives the original enquiry, a summary of prior rounds (generated by the orchestrator), and the latest round's responses. It critiques them and produces a revised answer.
   → `CritiqueResponse(has_disagreements: bool, disagreements: list[str], revised_response: str)`

   **Prompt structure per model**: original enquiry + LLM-generated summary of prior rounds + all latest-round responses in full. This keeps prompt size bounded regardless of round count.

   **Round summary generation**: After each critique round (starting from round 2), a cheap/fast model (GPT-4o-mini) summarizes the round's key agreements, disagreements, and shifts. This summary is included in the next round's prompts. Cost is minimal (~$0.001/summary) and tracked as a separate `llm_call` with role `summarizer`.

3. **Convergence check**: After each critique round, check if ALL models return `has_disagreements: False`. If yes → consensus reached. If no → repeat with updated responses.

4. **Termination**: Stop when consensus reached OR 20 rounds hit (hard cap). User can also set a custom max per session or in their settings (NULL = until consensus).

5. **Final output**: Present all models' final revised responses side by side. User picks their preferred answer.

**N calls per round**: N (each model sees all others in one prompt), NOT N*(N-1).

**Failure handling**: If a model fails (timeout 60s, API error), log error, drop from remaining rounds. Fail session only if <2 models remain.

**Orphaned session recovery**: Orchestrator updates `last_heartbeat_at` every 10s during execution. On app startup, any sessions stuck in non-terminal status (`responding`, `critiquing`) with `last_heartbeat_at` older than 5 minutes are marked `failed`. This handles container restarts, deploys, and crashes.

**Model Registry** resolves model → PydanticAI model instance:
1. Check user's own key for that provider (use provider's native API)
2. Fall back to user's OpenRouter key (translate slug: e.g. `gpt-4o` → `openai/gpt-4o` on OpenRouter API)
3. (Phase 6) Fall back to platform's single OpenRouter key for pay-per-use users (all models routed through OpenRouter)

OpenRouter is two things: a **provider** (users can select OpenRouter-exclusive models) and a **fallback route** (proxy other providers' models when the user lacks a direct key). The model registry handles this distinction:
- Direct provider key → use provider's `base_url` from the `providers` table
- OpenRouter fallback → use OpenRouter's `base_url`, prefix the model slug with the provider's slug (e.g. `anthropic/claude-sonnet-4-20250514`)
- The `providers` table stores each provider's slug, which doubles as the OpenRouter prefix

### SSE Streaming

`POST /api/sessions` returns session ID immediately, orchestrator runs as background `asyncio.Task`.
Client opens `GET /api/sessions/{id}/stream` as SSE (EventSource).

**Event replay from DB**: On connect, query all `llm_calls` for the session and send as events. If session is still running, poll DB every 1s for new `llm_calls` (by `created_at > last_seen`).

**No in-memory buffers, no NOTIFY/LISTEN** — simple DB polling avoids PgBouncer/connection-pooling issues with managed Postgres. 1s polling interval is fast enough for UX and lightweight on DB.

**Keepalive**: 15s SSE comment pings to prevent App Platform idle timeout.

SSE event types:
```
event: status_change
data: {"status": "responding", "round": 1}

event: response
data: {"model": "openai/gpt-4o", "round": 1, "response": {...}}

event: critique
data: {"model": "anthropic/claude-sonnet-4-20250514", "round": 2, "response": {...}}

event: consensus_reached
data: {"round": 3, "total_tokens": 12340, "total_cost": 0.042, "duration_ms": 18500}

event: max_rounds_reached
data: {"round": 20, "total_tokens": ..., "total_cost": ..., "duration_ms": ...}

event: error
data: {"model": "mistral/mistral-large", "error": "timeout", "models_remaining": 2}
```

**Logfire**: Auto-instrumented via PydanticAI + `logfire.instrument_fastapi(app)` + manual spans around each round.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/magic-link` | Send magic link email (rate limited: 3/email/15min) |
| POST | `/api/auth/verify` | Verify token → JWT (15min access + 7d refresh) |
| POST | `/api/auth/refresh` | Refresh JWT |
| GET/PUT | `/api/users/me` | Profile |
| GET/PUT | `/api/users/me/settings` | Default models, billing mode, max_rounds |
| GET/POST/DELETE | `/api/keys` | API key CRUD (Fernet encrypted, by provider_id) |
| POST | `/api/keys/{provider_id}/validate` | Test key validity (calls provider API) |
| GET | `/api/providers` | List providers |
| GET | `/api/models` | List available models (filterable by provider) |
| POST | `/api/sessions` | Start consensus flow → returns session ID |
| GET | `/api/sessions` | List past sessions (paginated) |
| GET | `/api/sessions/{id}` | Full session + all llm_calls |
| DELETE | `/api/sessions/{id}` | Hard delete session (CASCADE) |
| GET | `/api/sessions/{id}/stream` | SSE stream (replay from DB + 1s polling for live events) |
| GET | `/api/billing/usage` | Usage summary (by period, by model) |

---

## Deployment

**Local dev**: `docker compose up` runs Postgres + backend + frontend.

**Production** (~$32/mo):
- DigitalOcean App Platform: backend (FastAPI/uvicorn) + frontend (Next.js standalone) as app components
- Managed Postgres ($15/mo, 1GB RAM, 10GB storage)
- Auto-TLS, auto-deploy from GitHub, health checks built in

**CI/CD**: GitHub Actions for lint + test on every PR. App Platform auto-deploys main branch.

---

## Frontend Stack

- Next.js + Mantine
- Dark mode from day one (Mantine color scheme toggle)
- TanStack Query for data fetching
- Desktop-first layout, responsive

---

## Testing Philosophy

**Every task ships with tests. No exceptions. Prefer real infrastructure over mocks.**

We accept slower tests in exchange for realistic coverage. Mocks hide bugs.

- Backend: `pytest` + `pytest-asyncio` + `httpx` (async test client). Every endpoint, service, and agent tested.
- **Database**: Tests run against real Postgres (via Docker). No SQLite substitutes, no in-memory fakes.
- **Email (auth)**: Use Mailpit (local SMTP server in Docker Compose) instead of mocking Resend. Tests send real emails and verify delivery via Mailpit's API.
- **API key validation**: Hit real provider validation endpoints where feasible. Only stub when the provider has no free validation path.
- **PydanticAI agents**: Use `TestModel` for LLM calls only — these cost real money and are non-deterministic. This is the one acceptable fake.
- **Observability**: Use Logfire's testing exporter (not a mock — it's the official test harness).
- Frontend: Vitest + React Testing Library for components, Playwright for critical E2E flows.
- CI runs all tests on every PR. Red CI = no merge.
- Test files live next to source: `test_router.py` beside `router.py`, `ModelSelector.test.tsx` beside `ModelSelector.tsx`.

---

## Implementation Tasks

Ordered for fastest time-to-visible-results. Each task is a shippable increment with tests.

### Milestone 1 — Running skeleton (`docker compose up` works)

**Task 1.1 — Project scaffolding**
- `docker-compose.yml` (Postgres 16 + backend + frontend)
- `.env.example` with all required vars
- `.gitignore`
- `Makefile` (up, down, logs, migrate, test, lint)
- Backend: `pyproject.toml` with dependencies, `Dockerfile`, empty FastAPI app with `/health` endpoint
- Frontend: `bunx create-next-app`, `Dockerfile`
- **Tests**: health endpoint returns 200, frontend renders without crash
- **Verify**: `make up` → all 3 services healthy

**Task 1.2 — Database foundation**
- `app/config.py` (Pydantic Settings)
- `app/database.py` (SQLAlchemy async engine + session factory)
- Alembic init + config pointing to async engine
- ORM models: `providers`, `llm_models` (just these two first)
- First migration: create tables
- Seed migration: Big 4 + OpenRouter providers, initial model catalog
- **Tests**: migration runs cleanly, seed data queryable, rollback works
- **Verify**: `make migrate` → tables exist with seed data

### Milestone 2 — Auth works (can log in via magic link)

**Task 2.1 — User + auth DB models**
- ORM models: `users`, `user_settings`, `magic_links`, `refresh_tokens`
- Migration
- **Tests**: models create/read/cascade correctly

**Task 2.2 — Auth backend**
- `auth/service.py`: magic link generation, token hashing, JWT creation (access + refresh), email sending (SMTP locally via Mailpit, Resend in production)
- `auth/router.py`: `POST /api/auth/magic-link`, `POST /api/auth/verify`, `POST /api/auth/refresh`
- `auth/dependencies.py`: `get_current_user` dependency
- `auth/schemas.py`: request/response models
- Rate limiting: 3 magic links per email per 15min (DB check)
- Auto-create user on first verify (if email not in users table)
- **Tests**: full auth flow with Mailpit (real SMTP in Docker), expired token rejection, rate limit enforcement, refresh flow, invalid token handling
- **Verify**: curl magic-link → verify → get JWT → access protected endpoint

**Task 2.3 — Auth frontend**
- Mantine setup + dark mode color scheme toggle
- Login page: email input → request magic link → "check your email" state
- Verify page: reads token from URL params, calls verify endpoint, stores JWT
- Protected layout wrapper (redirects to login if no token)
- JWT refresh on 401
- Dashboard page (empty shell, just proves auth works)
- **Tests**: login form renders and submits, verify page handles success/error, protected redirect works
- **Verify**: full browser flow — enter email → click link → land on dashboard

### Milestone 2.5 — Deployed on App Platform (deploy early, deploy often)

**Task 2.5.1 — CI pipeline**
- GitHub Actions: lint (ruff + eslint) + test (pytest + vitest) on every PR
- **Tests**: pipeline itself runs green

**Task 2.5.2 — App Platform deployment**
- DigitalOcean App Platform app spec (`/.do/app.yaml`): backend + frontend as components, managed Postgres as DB
- Production environment variables configured (DATABASE_URL, JWT_SECRET, FERNET_KEY, RESEND_API_KEY)
- Health check endpoints verified on App Platform
- Auto-deploy from main branch
- **Tests**: deployed app returns 200 on health check, can complete magic link auth flow in prod
- **Verify**: visit https://your-domain.com → login works end-to-end in production

**From this point on, every merge to main auto-deploys. All subsequent milestones are verified in prod.**

---

### Milestone 3 — Can store API keys and configure models

**Task 3.1 — API keys backend**
- ORM model: `api_keys` + migration
- `keys/encryption.py`: Fernet encrypt/decrypt helpers
- `keys/service.py`: store (encrypt + validate by calling provider API), list (masked), delete
- `keys/router.py`: `GET/POST/DELETE /api/keys`, `POST /api/keys/{provider_id}/validate`
- `keys/schemas.py`
- **Tests**: encrypt/decrypt roundtrip, store + retrieve masked, validation against real provider endpoints where possible, duplicate key per provider rejected

**Task 3.2 — Providers, models, and user settings endpoints**
- `GET /api/providers` (from DB)
- `GET /api/models` (filterable by provider_id)
- `users/router.py`: `GET/PUT /api/users/me`, `GET/PUT /api/users/me/settings`
- `users/service.py`: update profile, manage default models (join table), billing mode, max_rounds
- **Tests**: providers list matches seed data, models filterable, settings round-trip correctly

**Task 3.3 — Model registry**
- `agent/model_registry.py`: resolve `(user, llm_model)` → PydanticAI model instance
- Resolution order: own key for provider → own OpenRouter key (with slug translation) → error (Phase 6 adds platform fallback)
- Slug translation: `gpt-4o` + provider `openai` → `openai/gpt-4o` on OpenRouter
- **Tests**: resolves with direct key, falls back to OpenRouter, raises error when no key available, slug translation correct

**Task 3.4 — Settings frontend**
- Settings page with tabs: API Keys, Default Models, Preferences
- API key form: add key per provider (masked display), test button, delete
- Model selector: pick default models from available catalog
- Round settings: "until consensus" toggle vs. specific round count
- **Tests**: forms render, submit, display masked keys, model selector works

### Milestone 4 — Core consensus works (CLI-testable, no UI yet)

**Task 4.1 — Session DB models**
- ORM models: `sessions`, `session_models`, `llm_calls` + migration
- **Tests**: session create with models, llm_call insert, cascade delete

**Task 4.2 — PydanticAI agents + prompts**
- `agent/types.py`: `InitialResponse`, `CritiqueResponse`, `RoundSummary` structured types
- `agent/consensus_agent.py`: responder agent, critic agent, summarizer agent (GPT-4o-mini)
- `agent/prompts.py`: system prompts for each role
- **Tests**: agents return correct structured types with `TestModel`, prompts render correctly with variable substitution

**Task 4.3 — ConsensusOrchestrator**
- `consensus/service.py`: full iterative convergence loop
  - Round 1: parallel initial responses
  - Round 2+: parallel critique/revise (each model sees all others)
  - After each critique round: GPT-4o-mini summarizes the round
  - Convergence: all `has_disagreements == False` → stop
  - Hard cap: 20 rounds → stop with `max_rounds_reached`
  - Failure: drop model on error/timeout, fail if <2 remain
  - Heartbeat: update `last_heartbeat_at` every 10s
  - `asyncio.Semaphore(10)` for concurrency control
- `consensus/pricing.py`: compute cost per call from DB pricing
- All llm_calls persisted to DB as they complete
- **Tests**: full flow with `TestModel` — convergence in N rounds, max rounds hit, model failure + skip, cost calculation, heartbeat updates. This is the most critical test suite.

**Task 4.4 — Session endpoints**
- `POST /api/sessions`: validate models (min 2, user has keys), create session, launch orchestrator as background task, return session ID
- `GET /api/sessions`: list user's sessions (paginated)
- `GET /api/sessions/{id}`: full session + all llm_calls
- `DELETE /api/sessions/{id}`: hard delete
- Orphaned session cleanup on app startup
- **Tests**: create session, poll until complete, verify all llm_calls recorded, pagination, delete cascades, orphan cleanup

### Milestone 5 — Live streaming in the browser (the "wow" moment)

**Task 5.1 — SSE backend**
- `GET /api/sessions/{id}/stream` via `sse-starlette`
- On connect: replay all existing `llm_calls` as typed events
- While session active: poll DB every 1s for new `llm_calls` (`created_at > last_seen`)
- 15s keepalive comment pings
- Session complete/failed → send terminal event → close
- **Tests**: SSE event stream matches expected sequence, replay works for completed sessions, keepalive pings sent

**Task 5.2 — Enquiry page frontend**
- Enquiry page: text input + model selector (from user's available models based on keys)
- Round override: "until consensus" or specific number
- Submit → `POST /api/sessions` → redirect to session page
- **Tests**: form validation (min 2 models), submit calls API, redirects

**Task 5.3 — Live consensus progress UI**
- `useConsensusStream` hook using `@microsoft/fetch-event-source` with JWT header
- `ConsensusProgress` component: shows rounds as they arrive, expanding cards per model
- Status indicators: which round, which models responded, convergence status
- Final state: side-by-side revised responses, user can read and compare
- **Tests**: hook processes SSE events correctly, progress component renders each state, final view displays all responses

**Task 5.4 — Dashboard + session detail**
- Dashboard: list of past sessions (status, models used, cost, date) with pagination
- Session detail page: full timeline of all rounds, expandable per-model responses
- **Tests**: session list renders, detail page shows all rounds, empty states

### Milestone 6 — Production-ready

**Task 6.1 — Observability**
- Logfire: `logfire.configure()` + `logfire.instrument_fastapi(app)`
- Manual spans: per-round, per-model-call, per-orchestrator-run
- Structured logging throughout
- **Tests**: verify spans are created (Logfire testing exporter)

**Task 6.2 — Usage tracking**
- `GET /api/billing/usage`: aggregate costs by period, by model, by session
- Frontend usage page: charts/tables showing spend breakdown
- **Tests**: aggregation queries return correct totals

**Task 6.3 — Error handling + polish**
- Graceful degradation on partial LLM failures (some models fail mid-session)
- Timeout handling with clear user feedback
- Loading/error/empty states across all pages
- Mobile responsive pass
- **Tests**: failure scenarios render correct UI states

### Milestone 7 — Pay-per-use (Phase 6, post-launch)

**Task 7.1 — Stripe metered billing**
- Stripe integration: free plan, usage-based metered billing
- Report token usage to Stripe after each session
- `billing_mode: pay_per_use` added to users
- **Tests**: usage reported correctly, Stripe webhook handling

**Task 7.2 — Spending caps + platform key**
- `PLATFORM_OPENROUTER_KEY` env var
- Model registry step 3: fall back to platform OpenRouter key
- Spending caps: $20/mo default, user-adjustable
- Block sessions when cap reached
- **Tests**: cap enforcement, fallback routing

**Task 7.3 — Billing frontend**
- Subscription management, spending cap settings, billing history
- **Tests**: cap adjustment, history display

---

## Verification (per milestone)

| Milestone | You can see |
|-----------|------------|
| 1 | `make up` → 3 services running, health checks green, seed data in DB |
| 2 | Enter email → receive magic link → click → land on dashboard, logged in |
| 2.5 | **Live on App Platform** — CI green, auto-deploy, auth works in prod |
| 3 | Settings page: store/mask/test API keys, select default models |
| 4 | `POST /api/sessions` → poll `GET /api/sessions/{id}` → see full consensus with all rounds |
| 5 | Submit enquiry in browser → watch live progress → see side-by-side final responses |
| 6 | Logfire traces, usage page, graceful error handling |
| 7 | Pay-per-use users can run sessions without their own keys, Stripe charges monthly |
