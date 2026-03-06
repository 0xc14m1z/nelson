# Unified Session View Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make completed sessions render identically to the live streaming view, with persisted structured data and real-time SSE streaming.

**Architecture:** Add explicit columns to LLMCall for structured data, delete the separate CompletedSessionView, build a state-reconstruction function that produces the same data structures as the streaming hook, and add a Next.js route handler for unbuffered SSE proxying.

**Tech Stack:** Python/SQLAlchemy/Alembic (backend), TypeScript/React/Next.js/Mantine (frontend)

---

### Task 1: Add structured columns to LLMCall model

**Files:**
- Modify: `backend/app/models/llm_call.py:10-31`

**Step 1: Add 4 nullable columns after `error` (line 27)**

```python
# After line 27 (error = Column(Text, nullable=True))
confidence = Column(Float, nullable=True)
key_points = Column(ARRAY(Text), nullable=True)
has_disagreements = Column(Boolean, nullable=True)
disagreements = Column(ARRAY(Text), nullable=True)
```

Add `Float, Boolean, ARRAY` to the SQLAlchemy imports at top of file.

**Step 2: Generate and review Alembic migration**

Run: `cd backend && uv run alembic revision --autogenerate -m "add structured columns to llm_calls"`

Verify the migration adds 4 columns. Then apply:

Run: `cd backend && uv run alembic upgrade head`

**Step 3: Commit**

```bash
git add backend/app/models/llm_call.py backend/alembic/versions/
git commit -m "feat: add structured columns to llm_calls table"
```

---

### Task 2: Persist structured data when saving LLM calls

**Files:**
- Modify: `backend/app/consensus/service.py:289-301` (responder save)
- Modify: `backend/app/consensus/service.py:439-451` (critic save)

**Step 1: Write failing test**

Create test in `backend/tests/consensus/test_structured_persistence.py`:

```python
import pytest
from sqlalchemy import select
from app.models.llm_call import LLMCall


@pytest.mark.asyncio
async def test_responder_persists_structured_data(db, seeded_user_with_models):
    """After a responder round, LLMCall rows should have confidence and key_points."""
    user, models = seeded_user_with_models
    from app.consensus.service import run_consensus
    from app.models.session import Session

    session = Session(
        user_id=user.id,
        enquiry="What is 2+2?",
        max_rounds=1,
    )
    db.add(session)
    await db.flush()

    # Attach models
    for m in models[:2]:
        session.models.append(m)
    await db.commit()

    await run_consensus(session.id, db)

    calls = (await db.execute(
        select(LLMCall).where(
            LLMCall.session_id == session.id,
            LLMCall.role == "responder",
        )
    )).scalars().all()

    assert len(calls) >= 1
    for call in calls:
        if call.error is None:
            assert call.confidence is not None
            assert call.key_points is not None
            assert isinstance(call.key_points, list)


@pytest.mark.asyncio
async def test_critic_persists_structured_data(db, seeded_user_with_models):
    """After a critic round, LLMCall rows should have has_disagreements and disagreements."""
    user, models = seeded_user_with_models
    from app.consensus.service import run_consensus
    from app.models.session import Session

    session = Session(
        user_id=user.id,
        enquiry="What is 2+2?",
        max_rounds=None,  # allow critique round
    )
    db.add(session)
    await db.flush()

    for m in models[:2]:
        session.models.append(m)
    await db.commit()

    await run_consensus(session.id, db)

    calls = (await db.execute(
        select(LLMCall).where(
            LLMCall.session_id == session.id,
            LLMCall.role == "critic",
        )
    )).scalars().all()

    # If consensus wasn't reached in round 1, there should be critic calls
    if calls:
        for call in calls:
            if call.error is None:
                assert call.has_disagreements is not None
                assert call.disagreements is not None
                assert isinstance(call.disagreements, list)
```

NOTE: This test depends on real infrastructure (TestModel). Check `backend/tests/conftest.py` for existing fixtures like `db` and see how `seeded_user_with_models` is set up. You may need to adapt the fixture names to match what exists. The important thing is to verify the columns get populated.

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/consensus/test_structured_persistence.py -v`

Expected: FAIL — the columns exist but are never populated.

**Step 3: Populate structured columns in service.py**

In `backend/app/consensus/service.py`, modify the responder save block (around line 289-301). The variable `output` is of type `InitialResponse` which has `confidence` and `key_points`. Add:

```python
call = LLMCall(
    session_id=session.id,
    llm_model_id=model.id,
    round_number=1,
    role="responder",
    prompt=prompt,
    response=output.response,
    input_tokens=usage.input_tokens or 0,
    output_tokens=usage.output_tokens or 0,
    cost=0,
    duration_ms=elapsed_ms,
    confidence=output.confidence,
    key_points=output.key_points,
)
```

Modify the critic save block (around line 439-451). The variable `output` is of type `CritiqueResponse` which has `has_disagreements` and `disagreements`. Add:

```python
call = LLMCall(
    session_id=session.id,
    llm_model_id=model.id,
    round_number=round_number,
    role="critic",
    prompt=prompt,
    response=output.revised_response,
    input_tokens=usage.input_tokens or 0,
    output_tokens=usage.output_tokens or 0,
    cost=0,
    duration_ms=elapsed_ms,
    has_disagreements=output.has_disagreements,
    disagreements=output.disagreements,
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/consensus/test_structured_persistence.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/consensus/service.py backend/tests/consensus/test_structured_persistence.py
git commit -m "feat: persist structured data in LLMCall rows"
```

---

### Task 3: Add structured fields to API response + fix catchup

**Files:**
- Modify: `backend/app/consensus/schemas.py:30-46` (LLMCallResponse)
- Modify: `backend/app/consensus/router.py:151` (catchup replay)
- Modify: `backend/app/consensus/router.py:213` (gap check replay)

**Step 1: Write failing test**

Add to `backend/tests/consensus/test_session_detail.py` (create if needed):

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_session_detail_includes_structured_fields(db, seeded_user_with_models, auth_headers):
    """GET /api/sessions/{id} should return structured fields in llm_calls."""
    user, models = seeded_user_with_models
    from app.consensus.service import run_consensus
    from app.models.session import Session

    session = Session(user_id=user.id, enquiry="What is 2+2?", max_rounds=1)
    db.add(session)
    await db.flush()
    for m in models[:2]:
        session.models.append(m)
    await db.commit()

    await run_consensus(session.id, db)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/sessions/{session.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    responder_calls = [c for c in data["llm_calls"] if c["role"] == "responder" and c["error"] is None]
    assert len(responder_calls) >= 1
    for call in responder_calls:
        assert "confidence" in call
        assert "key_points" in call
        assert call["confidence"] is not None
        assert isinstance(call["key_points"], list)
```

NOTE: Adapt fixture names to match existing test infrastructure. Check `backend/tests/conftest.py` for `auth_headers` or equivalent.

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/consensus/test_session_detail.py -v`

Expected: FAIL — `confidence` not in response.

**Step 3: Add fields to LLMCallResponse schema**

In `backend/app/consensus/schemas.py`, add 4 fields to `LLMCallResponse` (after `error` field, around line 43):

```python
class LLMCallResponse(BaseModel):
    id: UUID
    llm_model_id: UUID
    model_slug: str
    provider_slug: str
    round_number: int
    role: str
    prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    cost: float
    duration_ms: int
    error: str | None
    confidence: float | None
    key_points: list[str] | None
    has_disagreements: bool | None
    disagreements: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

**Step 4: Fix catchup replay to include structured data**

In `backend/app/consensus/router.py`, at the first catchup replay (around line 143-157), replace `"structured": {}` with:

```python
"structured": {
    k: v for k, v in {
        "confidence": call.confidence,
        "key_points": call.key_points,
        "has_disagreements": call.has_disagreements,
        "disagreements": call.disagreements,
    }.items() if v is not None
},
```

Do the same at the gap check replay (around line 204-219).

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/consensus/test_session_detail.py -v`

Expected: PASS

**Step 6: Run full backend test suite**

Run: `cd backend && uv run pytest -v`

Expected: All tests pass.

**Step 7: Commit**

```bash
git add backend/app/consensus/schemas.py backend/app/consensus/router.py backend/tests/consensus/
git commit -m "feat: include structured data in session detail API and catchup replay"
```

---

### Task 4: Add Next.js SSE route handler

**Files:**
- Create: `frontend/src/app/api/sessions/[id]/stream/route.ts`

**Step 1: Create the directory and route handler**

```typescript
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
  const authorization = request.headers.get("Authorization") || "";

  const upstream = await fetch(`${backendUrl}/api/sessions/${id}/stream`, {
    headers: { Authorization: authorization },
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.statusText, { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
```

**Step 2: Remove NEXT_PUBLIC_BACKEND_URL from useConsensusStream.ts**

In `frontend/src/hooks/useConsensusStream.ts`, revert lines 80-81 back to:

```typescript
const token = getAccessToken();
const source = new SSE(`/api/sessions/${sessionId}/stream`, {
```

Remove the `streamBase` line entirely.

**Step 3: Remove NEXT_PUBLIC_BACKEND_URL from docker-compose.yml**

In `docker-compose.yml`, delete line 65 (`NEXT_PUBLIC_BACKEND_URL: http://localhost:8000`).

**Step 4: Remove transpilePackages from next.config.ts**

In `frontend/next.config.ts`, remove the `transpilePackages: ["react-markdown", "remark-gfm"],` line.

**Step 5: Restart frontend and verify SSE streams in real-time**

Run: `docker compose up -d frontend`

Create a session and confirm tokens stream incrementally (not all at once at the end).

**Step 6: Commit**

```bash
git add frontend/src/app/api/sessions/\[id\]/stream/route.ts frontend/src/hooks/useConsensusStream.ts docker-compose.yml frontend/next.config.ts
git commit -m "feat: add SSE route handler for unbuffered streaming"
```

---

### Task 5: Delete CompletedSessionView, unify render path

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/[id]/page.tsx`
- Delete: `frontend/src/components/consensus/ChatMessage.tsx`

**Step 1: Add state-reconstruction function to page.tsx**

Add this function before `SessionPage`:

```typescript
interface ReconstructedState {
  models: Map<string, ModelStreamState>;
  phases: PhaseInfo[];
}

function buildStateFromCalls(
  llmCalls: SessionDetail["llm_calls"],
  modelNames: Map<string, string>,
): ReconstructedState {
  const models = new Map<string, ModelStreamState>();
  const roundsMap = new Map<number, Map<string, SessionDetail["llm_calls"][0]>>();

  for (const call of llmCalls) {
    if (call.role === "summarizer") continue;
    const key = `${call.llm_model_id}-${call.round_number}`;
    models.set(key, {
      llm_model_id: call.llm_model_id,
      round_number: call.round_number,
      role: call.role as "responder" | "critic" | "summarizer",
      text: call.response || "",
      isStreaming: false,
      isDone: true,
      error: call.error ?? null,
      structured: {
        ...(call.confidence != null ? { confidence: call.confidence } : {}),
        ...(call.key_points != null ? { key_points: call.key_points } : {}),
        ...(call.has_disagreements != null ? { has_disagreements: call.has_disagreements } : {}),
        ...(call.disagreements != null ? { disagreements: call.disagreements } : {}),
      },
      input_tokens: call.input_tokens,
      output_tokens: call.output_tokens,
      cost: call.cost,
      duration_ms: call.duration_ms,
    });

    // Group by round for phase reconstruction
    if (!roundsMap.has(call.round_number)) {
      roundsMap.set(call.round_number, new Map());
    }
    roundsMap.get(call.round_number)!.set(call.llm_model_id, call);
  }

  // Build phases — one per round
  const phases: PhaseInfo[] = [...roundsMap.entries()]
    .sort(([a], [b]) => a - b)
    .map(([roundNum, callsMap]) => {
      const calls = [...callsMap.values()];
      const role = calls[0]?.role ?? "responder";
      return {
        round_number: roundNum,
        phase: role === "responder" ? "responder_done" : "critic_done",
        models: calls
          .filter((c) => !c.error)
          .map((c) => ({
            llm_model_id: c.llm_model_id,
            model_name: modelNames.get(c.llm_model_id) ?? `${c.provider_slug}/${c.model_slug}`,
            ...(c.confidence != null ? { confidence: c.confidence } : {}),
            ...(c.key_points != null ? { key_points: c.key_points } : {}),
            ...(c.has_disagreements != null ? { has_disagreements: c.has_disagreements } : {}),
            ...(c.disagreements != null ? { disagreements: c.disagreements } : {}),
          })),
        roundSummary: null,
        collapsed: true,
      };
    });

  return { models, phases };
}
```

NOTE: You will need to import `ModelStreamState` and `PhaseInfo` from `@/hooks/useConsensusStream`.

**Step 2: Add structured fields to SessionDetail interface**

In the `SessionDetail` interface's `llm_calls` array type, add:

```typescript
confidence: number | null;
key_points: string[] | null;
has_disagreements: boolean | null;
disagreements: string[] | null;
```

**Step 3: Delete CompletedSessionView function**

Remove the entire `CompletedSessionView` function (lines ~59-183) and its related imports.

**Step 4: Rewrite the terminal branch of SessionPage**

Replace the terminal branch (the `if (isTerminal && session)` block) with:

```typescript
if (isTerminal && session) {
  const { models: completedModels, phases: completedPhases } = buildStateFromCalls(
    session.llm_calls,
    modelNames,
  );

  // Get the last round's models for the streaming columns
  let maxRound = 1;
  for (const model of completedModels.values()) {
    if (model.round_number > maxRound) maxRound = model.round_number;
  }
  const lastRoundEntries: Array<{ key: string; model: ModelStreamState }> = [];
  for (const [key, model] of completedModels) {
    if (model.round_number === maxRound) {
      lastRoundEntries.push({ key, model });
    }
  }

  return (
    <Stack gap="md">
      <Paper p="sm" radius="md" withBorder>
        <Text size="xs" c="dimmed" fw={600}>You</Text>
        <Text size="sm">{session.enquiry}</Text>
      </Paper>

      {completedPhases.slice(0, -1).map((phase, index) => (
        <PhaseDivider
          key={index}
          phase={phase}
          modelNames={modelNames}
          onToggle={() => {
            // Local toggle for completed phases
            completedPhases[index].collapsed = !completedPhases[index].collapsed;
            // Force re-render — we need local state for this
          }}
        />
      ))}

      <Box style={{ display: "flex", gap: 12, overflowX: "auto" }}>
        {lastRoundEntries.map(({ key, model }) => (
          <StreamingColumn
            key={key}
            model={model}
            displayName={modelNames.get(model.llm_model_id) ?? model.llm_model_id}
            allModelsDone={true}
          />
        ))}
      </Box>

      <ConsensusBanner
        type={session.status as "consensus_reached" | "max_rounds_reached" | "failed"}
        event={{
          status: session.status,
          current_round: session.current_round,
          total_input_tokens: session.total_input_tokens,
          total_output_tokens: session.total_output_tokens,
          total_cost: session.total_cost,
          total_duration_ms: session.total_duration_ms,
        }}
      />
    </Stack>
  );
}
```

IMPORTANT: The `onToggle` above won't work because `completedPhases` is not React state. You need to add local state for collapsed phases in the completed view. Add a `useState` for `collapsedPhases` and toggle by index, similar to how the streaming view works. The exact implementation is up to you — the key point is the same `PhaseDivider` and `StreamingColumn` components are used.

**Step 5: Delete ChatMessage.tsx**

Run: `rm frontend/src/components/consensus/ChatMessage.tsx`

Also check `frontend/src/types/session.ts` for `LLMCallEvent` and `MODEL_COLORS` — if `LLMCallEvent` is only used by ChatMessage, remove it. Keep `MODEL_COLORS` if used elsewhere.

**Step 6: Run frontend tests**

Run: `cd frontend && bunx vitest run`

Expected: All tests pass. Some tests may need updates if they reference removed components.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: unified session view — delete CompletedSessionView, render from DB state"
```

---

### Task 6: Manual end-to-end verification

**Step 1: Restart containers**

Run: `docker compose up -d`

**Step 2: Create a new session**

Log in as gino@pino.it. Create a session with 2-3 models. Ask: "Give me your best definition of context rot and how to fight it"

**Step 3: Verify live streaming**

- Tokens should stream incrementally (not all at once)
- Phase dividers should appear between rounds with structured data
- Streaming columns should show markdown-rendered text
- ConsensusBanner should appear at the end without crashing

**Step 4: Refresh the page**

- The page should look identical to the final state of the live view
- Phase dividers should show confidence, key_points, disagreements
- Streaming columns should show markdown-rendered responses with "Done" badges
- ConsensusBanner should show the same stats

**Step 5: Run full test suites**

Run: `cd backend && uv run pytest -v`
Run: `cd frontend && bunx vitest run`

Expected: All tests pass.

**Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
