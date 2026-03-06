"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Box,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useUserSettings } from "@/lib/hooks";
import type { Model } from "@/lib/hooks";

export default function NewSessionPage() {
  const router = useRouter();
  const { data: settings } = useUserSettings();
  const [enquiry, setEnquiry] = useState("");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [untilConsensus, setUntilConsensus] = useState(true);
  const [maxRounds, setMaxRounds] = useState<number>(5);
  const [initialized, setInitialized] = useState(false);

  // Fetch available models (user has keys for these providers)
  const { data: models = [] } = useQuery<Model[]>({
    queryKey: ["available-models"],
    queryFn: async () => {
      const res = await apiFetch("/api/models");
      return res.json();
    },
  });

  useEffect(() => {
    if (initialized || !settings || models.length === 0) return;

    const availableIds = new Set(models.map((m) => m.id));
    const validDefaults = settings.default_model_ids.filter((id) => availableIds.has(id));
    if (validDefaults.length > 0) setSelectedModelIds(validDefaults);

    setUntilConsensus(settings.max_rounds === null);
    if (settings.max_rounds !== null) setMaxRounds(settings.max_rounds);

    setInitialized(true);
  }, [initialized, settings, models]);

  // Group models by provider
  const grouped = models.reduce<Record<string, Model[]>>((acc, m) => {
    (acc[m.provider_slug] ??= []).push(m);
    return acc;
  }, {});

  const createSession = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enquiry,
          model_ids: selectedModelIds,
          max_rounds: untilConsensus ? null : maxRounds,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create session");
      }
      return res.json();
    },
    onSuccess: (data) => {
      router.push(`/sessions/${data.id}`);
    },
    onError: (err: Error) => {
      notifications.show({ title: "Error", message: err.message, color: "red" });
    },
  });

  const canSubmit = enquiry.trim().length > 0 && selectedModelIds.length >= 2;

  return (
    <Stack gap="lg" maw={700}>
      <Title order={2}>New Enquiry</Title>

      <Textarea
        label="Your question"
        placeholder="Ask anything..."
        minRows={4}
        autosize
        value={enquiry}
        onChange={(e) => setEnquiry(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSubmit) {
            createSession.mutate();
          }
        }}
      />

      <Box>
        <Text fw={500} mb="xs">Select models (minimum 2)</Text>
        {Object.entries(grouped).map(([provider, providerModels]) => (
          <Box key={provider} mb="sm">
            <Text size="sm" c="dimmed" tt="uppercase" mb={4}>{provider}</Text>
            <Checkbox.Group value={selectedModelIds} onChange={setSelectedModelIds}>
              <Stack gap={4}>
                {providerModels.map((m) => (
                  <Checkbox key={m.id} value={m.id} label={m.display_name} />
                ))}
              </Stack>
            </Checkbox.Group>
          </Box>
        ))}
      </Box>

      <Group>
        <Switch
          label="Run until consensus"
          checked={untilConsensus}
          onChange={(e) => setUntilConsensus(e.currentTarget.checked)}
        />
        {!untilConsensus && (
          <NumberInput
            label="Max rounds"
            value={maxRounds}
            onChange={(v) => setMaxRounds(Number(v))}
            min={2}
            max={20}
            w={100}
          />
        )}
      </Group>

      <Button
        onClick={() => createSession.mutate()}
        loading={createSession.isPending}
        disabled={!canSubmit}
      >
        Start Consensus
      </Button>
    </Stack>
  );
}
