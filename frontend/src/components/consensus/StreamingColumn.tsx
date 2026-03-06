import { useEffect, useRef } from "react";
import { Alert, Badge, Box, Group, Loader, Paper, ScrollArea, Text } from "@mantine/core";
import { IconAlertTriangle, IconCheck } from "@tabler/icons-react";
import type { ModelStreamState } from "@/hooks/useConsensusStream";

interface StreamingColumnProps {
  model: ModelStreamState;
  displayName: string;
  allModelsDone: boolean;
}

export function StreamingColumn({ model, displayName, allModelsDone }: StreamingColumnProps) {
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollTo({
        top: viewportRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [model.text]);

  return (
    <Paper
      p="md"
      radius="md"
      withBorder
      style={{
        flex: "1 1 0",
        minWidth: 350,
        display: "flex",
        flexDirection: "column",
        opacity: model.error ? 0.5 : 1,
      }}
    >
      {/* Header */}
      <Group justify="space-between" mb="sm">
        <Text fw={600} size="sm">
          {displayName}
        </Text>
        {model.isStreaming && <Loader size="xs" />}
        {model.isDone && !model.error && (
          <Badge
            color="green"
            variant="light"
            size="sm"
            leftSection={<IconCheck size={12} />}
          >
            Done
          </Badge>
        )}
        {model.isDone && model.error && (
          <Badge
            color="red"
            variant="light"
            size="sm"
            leftSection={<IconAlertTriangle size={12} />}
          >
            Error
          </Badge>
        )}
      </Group>

      {/* Scrollable text area */}
      <ScrollArea
        style={{ flex: 1, minHeight: 200 }}
        viewportRef={viewportRef}
      >
        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
          {model.text}
          {model.isStreaming && (
            <Box
              component="span"
              style={{
                animation: "blink 1s step-end infinite",
                fontWeight: 700,
              }}
            >
              |
            </Box>
          )}
        </Text>

        {model.isDone && !model.error && !allModelsDone && (
          <Text size="sm" c="dimmed" fs="italic" mt="xs">
            Waiting for other models to finish...
          </Text>
        )}
      </ScrollArea>

      {/* Error alert */}
      {model.isDone && model.error && (
        <Alert
          color="red"
          title="Model Error"
          mt="sm"
          icon={<IconAlertTriangle size={16} />}
        >
          <Text size="sm">{model.error}</Text>
        </Alert>
      )}
    </Paper>
  );
}
