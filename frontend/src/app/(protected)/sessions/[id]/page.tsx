"use client";

import { useEffect, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import { Box, Loader, Paper, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ChatMessage } from "@/components/consensus/ChatMessage";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { RoundDivider } from "@/components/consensus/RoundDivider";
import { useConsensusStream } from "@/hooks/useConsensusStream";
import type { SessionSummary } from "@/types/session";

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Fetch session metadata
  const { data: session } = useQuery<SessionSummary>({
    queryKey: ["session", id],
    queryFn: async () => {
      const res = await apiFetch(`/api/sessions/${id}`);
      return res.json();
    },
  });

  // Stream events
  const isTerminal = ["consensus_reached", "max_rounds_reached", "failed"].includes(
    session?.status || ""
  );
  const stream = useConsensusStream({ sessionId: id, enabled: !isTerminal });

  // Build color map: model_name -> index
  const colorMap = useMemo(() => {
    const map = new Map<string, number>();
    let idx = 0;
    for (const event of stream.events) {
      if (!map.has(event.model_name)) {
        map.set(event.model_name, idx++);
      }
    }
    return map;
  }, [stream.events]);

  // Group events by round
  const rounds = useMemo(() => {
    const grouped = new Map<number, typeof stream.events>();
    for (const event of stream.events) {
      const existing = grouped.get(event.round_number) || [];
      existing.push(event);
      grouped.set(event.round_number, existing);
    }
    return grouped;
  }, [stream.events]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [stream.events.length]);

  return (
    <Stack gap="md" maw={800}>
      {/* User enquiry as first message */}
      {session && (
        <Paper p="sm" radius="md" bg="blue.9" mb="xs">
          <Text size="xs" c="blue.3" fw={600}>You</Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>
      )}

      {/* Rounds */}
      {[...rounds.entries()].map(([roundNum, events]) => (
        <Box key={roundNum}>
          <RoundDivider round={roundNum} />
          {events.map((event) => (
            <ChatMessage
              key={event.id}
              event={event}
              colorIndex={colorMap.get(event.model_name) || 0}
            />
          ))}
        </Box>
      ))}

      {/* Loading indicator while active */}
      {stream.isConnected && (
        <Box ta="center" py="md">
          <Loader size="sm" />
          <Text size="xs" c="dimmed" mt={4}>Models are deliberating...</Text>
        </Box>
      )}

      {/* Terminal banner */}
      {stream.terminalEvent && (
        <ConsensusBanner
          type={stream.status as "consensus_reached" | "max_rounds_reached" | "failed"}
          event={stream.terminalEvent}
        />
      )}

      <div ref={bottomRef} />
    </Stack>
  );
}
