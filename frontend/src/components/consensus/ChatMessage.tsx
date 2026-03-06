import { Paper, Text } from "@mantine/core";
import type { LLMCallEvent } from "@/types/session";
import { MODEL_COLORS } from "@/types/session";

interface ChatMessageProps {
  event: LLMCallEvent;
  colorIndex: number;
  isUser?: boolean;
}

export function ChatMessage({ event, colorIndex }: ChatMessageProps) {
  const color = MODEL_COLORS[colorIndex % MODEL_COLORS.length];

  if (event.error) {
    return (
      <Paper p="sm" radius="md" bg="red.9" mb="xs">
        <Text size="xs" c="red.3" fw={600}>{event.model_name}</Text>
        <Text size="sm" c="red.1">Dropped: {event.error}</Text>
      </Paper>
    );
  }

  return (
    <Paper
      p="sm"
      radius="md"
      mb="xs"
      style={(theme) => ({
        borderLeft: `3px solid ${theme.colors[color][6]}`,
        backgroundColor: theme.colors.dark[7],
      })}
    >
      <Text size="xs" c={`${color}.4`} fw={600} mb={4}>
        {event.model_name}
        {event.role === "critic" && " (revised)"}
      </Text>
      <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
        {event.response}
      </Text>
    </Paper>
  );
}
