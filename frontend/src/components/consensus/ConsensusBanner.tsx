import { Alert, Group, Text } from "@mantine/core";
import type { TerminalEvent } from "@/types/session";

interface ConsensusBannerProps {
  type: "consensus_reached" | "max_rounds_reached" | "failed";
  event: TerminalEvent;
}

export function ConsensusBanner({ type, event }: ConsensusBannerProps) {
  const config = {
    consensus_reached: {
      color: "green",
      title: "Consensus Reached",
      message: `Models converged after ${event.current_round} rounds.`,
    },
    max_rounds_reached: {
      color: "yellow",
      title: "Max Rounds Reached",
      message: `No consensus after ${event.current_round} rounds.`,
    },
    failed: {
      color: "red",
      title: "Session Failed",
      message: "Too few models remaining to continue.",
    },
  }[type];

  return (
    <Alert color={config.color} title={config.title} my="md">
      <Text size="sm">{config.message}</Text>
      <Group gap="lg" mt="xs">
        <Text size="xs" c="dimmed">
          Tokens: {event.total_input_tokens + event.total_output_tokens}
        </Text>
        <Text size="xs" c="dimmed">
          Cost: ${event.total_cost.toFixed(4)}
        </Text>
        <Text size="xs" c="dimmed">
          Duration: {(event.total_duration_ms / 1000).toFixed(1)}s
        </Text>
      </Group>
    </Alert>
  );
}
