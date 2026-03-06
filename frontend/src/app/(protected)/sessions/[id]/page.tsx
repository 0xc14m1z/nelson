"use client";

import { Fragment, useMemo } from "react";
import { useParams } from "next/navigation";
import {
  Box,
  Divider,
  Loader,
  Paper,
  Stack,
  Text,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { StreamingColumn } from "@/components/consensus/StreamingColumn";
import { useConsensusStream } from "@/hooks/useConsensusStream";
import type { ModelStreamState } from "@/hooks/useConsensusStream";
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

function buildModelsFromCalls(
  llmCalls: SessionDetail["llm_calls"],
): Map<string, ModelStreamState> {
  const models = new Map<string, ModelStreamState>();

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
  }

  return models;
}

/* ------------------------------------------------------------------ */
/*  Helper: group models by round and compute per-round done state    */
/* ------------------------------------------------------------------ */

function groupByRound(models: Map<string, ModelStreamState>) {
  const rounds = new Map<number, Array<{ key: string; model: ModelStreamState }>>();
  for (const [key, model] of models) {
    const arr = rounds.get(model.round_number) ?? [];
    arr.push({ key, model });
    rounds.set(model.round_number, arr);
  }
  return [...rounds.entries()].sort(([a], [b]) => a - b);
}

function roundLabel(roundNumber: number, role: string) {
  if (role === "summarizer") return "Final Consensus";
  if (role === "critic") return `Round ${roundNumber} — Critique`;
  return `Round ${roundNumber} — Initial Responses`;
}

/* ------------------------------------------------------------------ */
/*  Main page component                                               */
/* ------------------------------------------------------------------ */

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();

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

  // Reconstruct state from API data for completed sessions
  const reconstructedModels = useMemo(() => {
    if (!isTerminal || !session) return null;
    return buildModelsFromCalls(session.llm_calls);
  }, [isTerminal, session]);

  // Pick the models map: reconstructed for completed, stream for live
  const modelsMap = isTerminal && reconstructedModels ? reconstructedModels : stream.models;
  const rounds = useMemo(() => groupByRound(modelsMap), [modelsMap]);

  /* ---------- Shared render for both live and completed ---------- */
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

      {/* All rounds, each with columns */}
      {rounds.map(([roundNum, entries], roundIndex) => {
        const allDone = entries.every((e) => e.model.isDone);
        const role = entries[0]?.model.role ?? "responder";

        return (
          <Fragment key={roundNum}>
            {/* Divider between rounds */}
            {roundIndex > 0 && (
              <Divider
                label={roundLabel(roundNum, role)}
                labelPosition="center"
                my="xs"
              />
            )}

            {/* Columns for this round */}
            <Box
              style={{
                display: "flex",
                gap: 12,
                overflowX: "auto",
              }}
            >
              {entries.map(({ key, model }) => (
                <StreamingColumn
                  key={key}
                  model={model}
                  displayName={modelNames.get(model.llm_model_id) ?? model.llm_model_id}
                  allModelsDone={allDone}
                />
              ))}
            </Box>
          </Fragment>
        );
      })}

      {/* Loading indicator (live only) */}
      {!isTerminal && stream.isConnected && rounds.length === 0 && (
        <Box ta="center" py="md">
          <Loader size="sm" />
          <Text size="xs" c="dimmed" mt={4}>
            Waiting for models to start...
          </Text>
        </Box>
      )}

      {/* Terminal banner */}
      {isTerminal && session && (
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
      )}
      {!isTerminal && stream.terminalEvent && (
        <ConsensusBanner
          type={stream.status as "consensus_reached" | "max_rounds_reached" | "failed"}
          event={stream.terminalEvent}
        />
      )}
    </Stack>
  );
}
