# Unified Session View Design

## Problem

The session page has two completely different render paths for live (streaming) and completed sessions. The completed view is a separate, inferior component that:

1. Doesn't render markdown
2. Doesn't show structured data (confidence, key_points, disagreements)
3. Doesn't show phase dividers or round summaries
4. Looks completely different from the live streaming view

Additionally:
- Structured data (confidence, key_points, disagreements) is never persisted to the DB — it's only available during live streaming
- Next.js `rewrites` buffers SSE responses, preventing real-time token streaming
- `ConsensusBanner` crashes on undefined fields, killing the entire page

## Solution: Approach A — Unified View with DB Persistence

### 1. Backend: Explicit Columns on LLMCall

Add 4 nullable columns to the `LLMCall` model:

- `confidence: Float` — responder's confidence score (0-100)
- `key_points: ARRAY(Text)` — responder's key points
- `has_disagreements: Boolean` — critic's disagreement flag
- `disagreements: ARRAY(Text)` — critic's disagreement list

Alembic migration to add these columns.

**Persistence:** In `consensus/service.py`, populate these columns from the parsed PydanticAI agent output when saving LLM calls.

**API schema:** Add these 4 fields to `LLMCallResponse` so `GET /api/sessions/{id}` returns them.

**Catchup fix:** In the stream endpoint's catchup logic, populate the `structured` dict from these DB columns instead of sending empty `{}`.

### 2. Frontend: Delete CompletedSessionView, One Render Path

Delete `CompletedSessionView` from `page.tsx`.

New function `buildStateFromCalls(llm_calls, modelNames)` reconstructs the same data structures the streaming hook produces:

- `Map<string, ModelStreamState>` — one entry per model per round, `isDone: true`, `isStreaming: false`, text from `response`, structured fields mapped in
- `PhaseInfo[]` — one per round, models array populated from calls' structured data, collapsed by default

Session page logic:
- If terminal: build state from API response, render same components (`PhaseDivider`, `StreamingColumn`, `ConsensusBanner`)
- If live: use `useConsensusStream` hook, render same components

JSX is identical — only the data source differs.

### 3. SSE Proxy: Next.js Route Handler

Add `frontend/src/app/api/sessions/[id]/stream/route.ts` — a server-side route handler that:

- Reads `Authorization` header from request
- Fetches backend SSE endpoint directly (`http://backend:8000/...`)
- Returns `Response` with backend's readable stream and `Content-Type: text/event-stream`
- No buffering

Frontend SSE client stays on `/api/sessions/{id}/stream` (same URL), but now hits this route handler instead of the rewrite. All other `/api/*` requests continue through rewrites.

### 4. Cleanup

- Remove `NEXT_PUBLIC_BACKEND_URL` from `docker-compose.yml` and `useConsensusStream.ts`
- Remove `ChatMessage.tsx` (unused)
- Remove `MarkdownRenderer.tsx` (temporary file from dynamic import attempt)
- Remove `transpilePackages` from `next.config.ts`
- Keep `ConsensusBanner` `?? 0` guards
- Keep `MarkdownContent.tsx` with direct import (react-markdown + remark-gfm + Mantine mappings)
