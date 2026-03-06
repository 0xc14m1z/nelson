"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ActionIcon,
  Box,
  Group,
  NumberInput,
  Pill,
  Popover,
  ScrollArea,
  Stack,
  Switch,
  Text,
  Textarea,
  UnstyledButton,
} from "@mantine/core";
import { IconArrowRight, IconCheck, IconPlus } from "@tabler/icons-react";
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

  const toggleModel = (id: string) => {
    setSelectedModelIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

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
      <Textarea
        placeholder="Ask anything..."
        radius="xl"
        size="md"
        autosize
        minRows={1}
        value={enquiry}
        onChange={(e) => setEnquiry(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSubmit) {
            e.preventDefault();
            createSession.mutate();
          }
        }}
        rightSectionWidth={42}
        rightSection={
          <ActionIcon
            size={32}
            radius="xl"
            variant="filled"
            disabled={!canSubmit}
            loading={createSession.isPending}
            onClick={() => createSession.mutate()}
            aria-label="Start consensus"
          >
            <IconArrowRight size={18} stroke={1.5} />
          </ActionIcon>
        }
        styles={{
          input: { fieldSizing: "content" as never },
        }}
      />

      <Box>
        <Text fw={500} mb="xs">Models</Text>
        <Group gap="xs">
          {selectedModelIds
            .map((id) => models.find((m) => m.id === id))
            .filter((m): m is Model => m !== undefined)
            .map((m) => (
              <Pill
                key={m.id}
                withRemoveButton
                onRemove={() => toggleModel(m.id)}
                removeButtonProps={{
                  disabled: selectedModelIds.length <= 2,
                }}
              >
                {m.display_name}
              </Pill>
            ))}
          <Popover width={300} position="bottom-start" shadow="md">
            <Popover.Target>
              <ActionIcon variant="subtle" size="sm" aria-label="Add model">
                <IconPlus size={16} />
              </ActionIcon>
            </Popover.Target>
            <Popover.Dropdown>
              <ScrollArea.Autosize mah={300}>
                {Object.entries(grouped).map(([provider, providerModels]) => (
                  <Box key={provider} mb="xs">
                    <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>
                      {provider}
                    </Text>
                    {providerModels.map((m) => {
                      const selected = selectedModelIds.includes(m.id);
                      return (
                        <UnstyledButton
                          key={m.id}
                          onClick={() => {
                            if (selected && selectedModelIds.length <= 2) return;
                            toggleModel(m.id);
                          }}
                          w="100%"
                          py={4}
                          px="xs"
                          style={{ borderRadius: 4 }}
                        >
                          <Group justify="space-between">
                            <Text size="sm">{m.display_name}</Text>
                            {selected && <IconCheck size={16} color="var(--mantine-color-blue-6)" />}
                          </Group>
                        </UnstyledButton>
                      );
                    })}
                  </Box>
                ))}
              </ScrollArea.Autosize>
            </Popover.Dropdown>
          </Popover>
        </Group>
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
    </Stack>
  );
}
