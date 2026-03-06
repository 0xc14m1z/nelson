import { Divider, Text } from "@mantine/core";

interface RoundDividerProps {
  round: number;
  label?: string;
}

export function RoundDivider({ round, label }: RoundDividerProps) {
  return (
    <Divider
      my="md"
      label={
        <Text size="xs" c="dimmed">
          {label || `Round ${round}${round > 1 ? " — Critique" : " — Initial Responses"}`}
        </Text>
      }
      labelPosition="center"
    />
  );
}
