import { ActionIcon, Badge, Box, Collapse, Group, List, Paper, Text } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import type { PhaseInfo } from "@/hooks/useConsensusStream";

interface PhaseDividerProps {
  phase: PhaseInfo;
  modelNames: Map<string, string>;
  onToggle: () => void;
}

export function PhaseDivider({ phase, modelNames, onToggle }: PhaseDividerProps) {
  const completedCount = phase.models.length;
  const failedCount = 0; // Could be extended when failure info is in PhaseChangeEvent

  const label =
    `Round ${phase.round_number}${phase.round_number > 1 ? " — Critique" : " — Initial Responses"}`;

  return (
    <Paper
      p="sm"
      radius="md"
      my="md"
      withBorder
      style={{ width: "100%" }}
    >
      {/* Header bar */}
      <Group justify="space-between">
        <Group gap="sm">
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={onToggle}
            aria-label="Toggle phase details"
          >
            {phase.collapsed ? (
              <IconChevronRight size={16} />
            ) : (
              <IconChevronDown size={16} />
            )}
          </ActionIcon>
          <Text fw={600} size="sm">
            {label}
          </Text>
        </Group>
        <Group gap="xs">
          <Badge color="green" variant="light" size="sm">
            {completedCount} completed
          </Badge>
          {failedCount > 0 && (
            <Badge color="red" variant="light" size="sm">
              {failedCount} failed
            </Badge>
          )}
        </Group>
      </Group>

      {/* Expandable details */}
      <Collapse in={!phase.collapsed}>
        <Box mt="sm">
          {/* Per-model structured data */}
          {phase.models.map((m) => (
            <Paper
              key={m.llm_model_id}
              p="xs"
              radius="sm"
              mb="xs"
              withBorder
            >
              <Text size="sm" fw={500} mb={4}>
                {modelNames.get(m.llm_model_id) ?? m.model_name}
              </Text>

              {m.confidence !== undefined && (
                <Text size="xs" c="dimmed">
                  Confidence: {m.confidence}%
                </Text>
              )}

              {m.key_points && m.key_points.length > 0 && (
                <Box mt={4}>
                  <Text size="xs" c="dimmed" fw={500}>
                    Key Points:
                  </Text>
                  <List size="xs" withPadding>
                    {m.key_points.map((point, i) => (
                      <List.Item key={i}>{point}</List.Item>
                    ))}
                  </List>
                </Box>
              )}

              {m.disagreements && m.disagreements.length > 0 && (
                <Box mt={4}>
                  <Text size="xs" c="dimmed" fw={500}>
                    Disagreements:
                  </Text>
                  <List size="xs" withPadding>
                    {m.disagreements.map((d, i) => (
                      <List.Item key={i}>{d}</List.Item>
                    ))}
                  </List>
                </Box>
              )}
            </Paper>
          ))}

          {/* Round summary */}
          {phase.roundSummary && (
            <Paper
              p="xs"
              radius="sm"
              mt="xs"
              withBorder
            >
              <Text size="sm" fw={500} mb={4}>
                Round Summary
              </Text>

              {phase.roundSummary.agreements.length > 0 && (
                <Box mb={4}>
                  <Text size="xs" c="green" fw={500}>
                    Agreements:
                  </Text>
                  <List size="xs" withPadding>
                    {phase.roundSummary.agreements.map((a, i) => (
                      <List.Item key={i}>{a}</List.Item>
                    ))}
                  </List>
                </Box>
              )}

              {phase.roundSummary.disagreements.length > 0 && (
                <Box mb={4}>
                  <Text size="xs" c="red" fw={500}>
                    Disagreements:
                  </Text>
                  <List size="xs" withPadding>
                    {phase.roundSummary.disagreements.map((d, i) => (
                      <List.Item key={i}>{d}</List.Item>
                    ))}
                  </List>
                </Box>
              )}

              {phase.roundSummary.shifts.length > 0 && (
                <Box>
                  <Text size="xs" c="yellow" fw={500}>
                    Shifts:
                  </Text>
                  <List size="xs" withPadding>
                    {phase.roundSummary.shifts.map((s, i) => (
                      <List.Item key={i}>{s}</List.Item>
                    ))}
                  </List>
                </Box>
              )}
            </Paper>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
