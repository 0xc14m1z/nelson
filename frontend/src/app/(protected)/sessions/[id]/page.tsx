"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  Box,
  Loader,
  Paper,
  Stack,
  Text,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { PhaseDivider } from "@/components/consensus/PhaseDivider";
import { StreamingColumn } from "@/components/consensus/StreamingColumn";
import { useConsensusStream } from "@/hooks/useConsensusStream";
import type { ModelStreamState, PhaseInfo } from "@/hooks/useConsensusStream";
import type { SessionSummary } from "@/types/session";

/* ------------------------------------------------------------------ */
/*  Types for session detail (completed session with llm_calls)       */
/* ------------------------------------------------------------------ */

interface SessionDetail extends SessionSummary {
  llm_calls: Array<{
    id: string;
    llm_model_id: string;
    model_slug: string;
    provider_slug: string;
    round_number: number;
    role: string;
    prompt: string;
    response: string;
    error: string | null;
    input_tokens: number;
    output_tokens: number;
    cost: number;
    duration_ms: number;
    confidence: number | null;
    key_points: string[] | null;
    has_disagreements: boolean | null;
    disagreements: string[] | null;
    created_at: string;
  }>;
}

interface CatalogModel {
  id: string;
  provider_slug: string;
  slug: string;
  display_name: string;
}

/* ------------------------------------------------------------------ */
/*  State reconstruction from API data                                */
/* ------------------------------------------------------------------ */

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

    if (!roundsMap.has(call.round_number)) {
      roundsMap.set(call.round_number, new Map());
    }
    roundsMap.get(call.round_number)!.set(call.llm_model_id, call);
  }

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

/* ------------------------------------------------------------------ */
/*  Main page component                                               */
/* ------------------------------------------------------------------ */

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();

  // Fetch session metadata (summary for live, detail for completed)
  const { data: session } = useQuery<SessionDetail>({
    queryKey: ["session", id],
    queryFn: async () => {
      const res = await apiFetch(`/api/sessions/${id}`);
      return res.json();
    },
  });

  const isTerminal = ["consensus_reached", "max_rounds_reached", "failed"].includes(
    session?.status || "",
  );

  // Fetch all models for name resolution
  const { data: catalogModels } = useQuery<CatalogModel[]>({
    queryKey: ["models"],
    queryFn: async () => {
      const res = await apiFetch("/api/models");
      return res.json();
    },
  });

  const modelNames = useMemo(() => {
    const map = new Map<string, string>();
    if (catalogModels) {
      for (const m of catalogModels) {
        map.set(m.id, `${m.provider_slug}/${m.slug}`);
      }
    }
    return map;
  }, [catalogModels]);

  // Stream events (only when session is not terminal)
  const stream = useConsensusStream({ sessionId: id, enabled: !isTerminal });
  const streamModels = stream.models;

  // Derive current round from models map
  const currentRound = useMemo(() => {
    let max = 1;
    for (const model of streamModels.values()) {
      if (model.round_number > max) max = model.round_number;
    }
    return max;
  }, [streamModels]);

  // Current round models (for live streaming columns)
  const currentRoundModels = useMemo(() => {
    const entries: Array<{
      key: string;
      model: (typeof streamModels extends Map<string, infer V> ? V : never);
    }> = [];
    for (const [key, model] of streamModels) {
      if (model.round_number === currentRound) {
        entries.push({ key, model });
      }
    }
    return entries;
  }, [streamModels, currentRound]);

  const allCurrentDone = useMemo(() => {
    if (currentRoundModels.length === 0) return false;
    return currentRoundModels.every((e) => e.model.isDone);
  }, [currentRoundModels]);

  // Reconstruct state from API data for completed sessions
  const reconstructed = useMemo(() => {
    if (!isTerminal || !session) return null;
    return buildStateFromCalls(session.llm_calls, modelNames);
  }, [isTerminal, session, modelNames]);

  const [collapsedPhases, setCollapsedPhases] = useState<Record<number, boolean>>({});

  const completedPhases = useMemo(() => {
    if (!reconstructed) return [];
    return reconstructed.phases.map((p, i) => ({
      ...p,
      collapsed: collapsedPhases[i] ?? true,
    }));
  }, [reconstructed, collapsedPhases]);

  const toggleCompletedPhase = useCallback((index: number) => {
    setCollapsedPhases((prev) => ({ ...prev, [index]: !(prev[index] ?? true) }));
  }, []);

  /* ---------- Terminal: completed session view ---------- */
  if (isTerminal && session && reconstructed) {
    // All phases except the last are shown as PhaseDividers (collapsed)
    // The last round's models are shown as StreamingColumns
    const allPhases = completedPhases;
    const pastPhases = allPhases.slice(0, -1);
    const lastPhase = allPhases[allPhases.length - 1];

    // Get the last round's models from the reconstructed map
    const lastRoundModels: Array<{ key: string; model: ModelStreamState }> = [];
    if (lastPhase) {
      for (const [key, model] of reconstructed.models) {
        if (model.round_number === lastPhase.round_number) {
          lastRoundModels.push({ key, model });
        }
      }
    }

    return (
      <Stack gap="md">
        {/* Enquiry header */}
        <Paper p="sm" radius="md" withBorder>
          <Text size="xs" c="dimmed" fw={600}>
            You
          </Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>

        {/* Past phases as PhaseDividers */}
        {pastPhases.map((phase, index) => (
          <PhaseDivider
            key={index}
            phase={phase}
            modelNames={modelNames}
            onToggle={() => toggleCompletedPhase(index)}
          />
        ))}

        {/* Last round's models as StreamingColumns */}
        {lastRoundModels.length > 0 && (
          <Box
            style={{
              display: "flex",
              gap: 12,
              overflowX: "auto",
            }}
          >
            {lastRoundModels.map(({ key, model }) => (
              <StreamingColumn
                key={key}
                model={model}
                displayName={modelNames.get(model.llm_model_id) ?? model.llm_model_id}
                allModelsDone={true}
              />
            ))}
          </Box>
        )}

        {/* Terminal banner */}
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

  /* ---------- Live: streaming view ---------- */
  return (
    <Stack gap="md">
      {/* Enquiry header */}
      {session && (
        <Paper p="sm" radius="md" withBorder>
          <Text size="xs" c="dimmed" fw={600}>
            You
          </Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>
      )}

      {/* Completed phases (past rounds) */}
      {stream.phases.map((phase, index) => (
        <PhaseDivider
          key={index}
          phase={phase}
          modelNames={modelNames}
          onToggle={() => stream.togglePhase(index)}
        />
      ))}

      {/* Current round streaming columns */}
      {currentRoundModels.length > 0 && (
        <Box
          style={{
            display: "flex",
            gap: 12,
            overflowX: "auto",
          }}
        >
          {currentRoundModels.map(({ key, model }) => (
            <StreamingColumn
              key={key}
              model={model}
              displayName={modelNames.get(model.llm_model_id) ?? model.llm_model_id}
              allModelsDone={allCurrentDone}
            />
          ))}
        </Box>
      )}

      {/* Loading indicator */}
      {stream.isConnected && currentRoundModels.length === 0 && (
        <Box ta="center" py="md">
          <Loader size="sm" />
          <Text size="xs" c="dimmed" mt={4}>
            Waiting for models to start...
          </Text>
        </Box>
      )}

      {/* Terminal banner */}
      {stream.terminalEvent && (
        <ConsensusBanner
          type={stream.status as "consensus_reached" | "max_rounds_reached" | "failed"}
          event={stream.terminalEvent}
        />
      )}
    </Stack>
  );
}
