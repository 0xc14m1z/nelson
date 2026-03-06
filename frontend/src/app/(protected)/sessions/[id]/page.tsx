"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  ActionIcon,
  Box,
  Collapse,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
} from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { PhaseDivider } from "@/components/consensus/PhaseDivider";
import { StreamingColumn } from "@/components/consensus/StreamingColumn";
import { useConsensusStream } from "@/hooks/useConsensusStream";
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
/*  Completed session view                                            */
/* ------------------------------------------------------------------ */

function CompletedSessionView({
  session,
  modelNames,
}: {
  session: SessionDetail;
  modelNames: Map<string, string>;
}) {
  // Group llm_calls by round_number
  const rounds = useMemo(() => {
    const grouped = new Map<number, SessionDetail["llm_calls"]>();
    for (const call of session.llm_calls) {
      if (call.role === "summarizer") continue;
      const existing = grouped.get(call.round_number) || [];
      existing.push(call);
      grouped.set(call.round_number, existing);
    }
    return [...grouped.entries()].sort(([a], [b]) => a - b);
  }, [session.llm_calls]);

  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});

  const toggleRound = (roundNum: number) => {
    setCollapsed((prev) => ({ ...prev, [roundNum]: !prev[roundNum] }));
  };

  return (
    <Stack gap="md">
      {rounds.map(([roundNum, calls]) => {
        const isCollapsed = collapsed[roundNum] ?? false;
        const label =
          roundNum === 1
            ? `Round ${roundNum} \u2014 Initial Responses`
            : `Round ${roundNum} \u2014 Critique`;

        return (
          <Box key={roundNum}>
            {/* Round header */}
            <Paper
              p="sm"
              radius="md"
              withBorder
              style={{ cursor: "pointer" }}
              onClick={() => toggleRound(roundNum)}
            >
              <Group gap="sm">
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  aria-label={`Toggle round ${roundNum}`}
                >
                  {isCollapsed ? (
                    <IconChevronRight size={16} />
                  ) : (
                    <IconChevronDown size={16} />
                  )}
                </ActionIcon>
                <Text fw={600} size="sm">
                  {label}
                </Text>
                <Text size="xs" c="dimmed">
                  ({calls.length} model{calls.length !== 1 ? "s" : ""})
                </Text>
              </Group>
            </Paper>

            {/* Round columns */}
            <Collapse in={!isCollapsed}>
              <Box
                mt="sm"
                style={{
                  display: "flex",
                  gap: 12,
                  overflowX: "auto",
                }}
              >
                {calls.map((call) => {
                  const displayName =
                    modelNames.get(call.llm_model_id) ??
                    `${call.provider_slug}/${call.model_slug}`;

                  return (
                    <Paper
                      key={call.id}
                      p="md"
                      radius="md"
                      style={{
                        flex: "1 1 0",
                        minWidth: 350,
                        display: "flex",
                        flexDirection: "column",
                        opacity: call.error ? 0.5 : 1,
                      }}
                    >
                      <Text fw={600} size="sm" mb="sm">
                        {displayName}
                      </Text>
                      <ScrollArea style={{ flex: 1, minHeight: 200 }}>
                        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                          {call.error ?? call.response}
                        </Text>
                      </ScrollArea>
                    </Paper>
                  );
                })}
              </Box>
            </Collapse>
          </Box>
        );
      })}

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

  /* ---------- Terminal: completed session view ---------- */
  if (isTerminal && session) {
    return (
      <Stack gap="md">
        {/* Enquiry header */}
        <Paper p="sm" radius="md" withBorder>
          <Text size="xs" c="dimmed" fw={600}>
            You
          </Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>

        <CompletedSessionView session={session} modelNames={modelNames} />
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
