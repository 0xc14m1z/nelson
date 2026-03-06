"use client";

import { useRouter } from "next/navigation";
import {
  Badge,
  Button,
  Group,
  Paper,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { SessionSummary } from "@/types/session";

const STATUS_COLORS: Record<string, string> = {
  pending: "gray",
  responding: "blue",
  critiquing: "yellow",
  consensus_reached: "green",
  max_rounds_reached: "orange",
  failed: "red",
};

export default function SessionsPage() {
  const router = useRouter();

  const { data } = useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const res = await apiFetch("/api/sessions");
      return res.json();
    },
  });

  const sessions: SessionSummary[] = data?.sessions || [];

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Sessions</Title>
        <Button onClick={() => router.push("/sessions/new")}>New Enquiry</Button>
      </Group>

      {sessions.length === 0 && (
        <Text c="dimmed">No sessions yet. Start your first enquiry!</Text>
      )}

      {sessions.map((s) => (
        <Paper
          key={s.id}
          p="md"
          radius="md"
          withBorder
          style={{ cursor: "pointer" }}
          onClick={() => router.push(`/sessions/${s.id}`)}
        >
          <Group justify="space-between" mb={4}>
            <Text fw={500} lineClamp={1} style={{ flex: 1 }}>
              {s.enquiry}
            </Text>
            <Badge color={STATUS_COLORS[s.status] || "gray"} variant="light">
              {s.status.replace(/_/g, " ")}
            </Badge>
          </Group>
          <Group gap="lg">
            <Text size="xs" c="dimmed">{s.model_ids.length} models</Text>
            <Text size="xs" c="dimmed">{s.current_round} rounds</Text>
            <Text size="xs" c="dimmed">${s.total_cost.toFixed(4)}</Text>
            <Text size="xs" c="dimmed">
              {new Date(s.created_at).toLocaleDateString()}
            </Text>
          </Group>
        </Paper>
      ))}
    </Stack>
  );
}
