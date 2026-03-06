"use client";

import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Container,
  Group,
  Modal,
  NumberInput,
  Paper,
  Select,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  useProviders,
  useApiKeys,
  useModels,
  useUserSettings,
  useStoreKey,
  useDeleteKey,
  useValidateKey,
  useUpdateSettings,
} from "../../../lib/hooks";

/* ─── API Keys Tab ─── */

function ApiKeysTab() {
  const { data: providers = [], isLoading: providersLoading } = useProviders();
  const { data: apiKeys = [], isLoading: keysLoading } = useApiKeys();
  const storeKey = useStoreKey();
  const deleteKey = useDeleteKey();
  const validateKey = useValidateKey();

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  function getKeyForProvider(providerId: string) {
    return apiKeys.find((k) => k.provider_id === providerId);
  }

  function openModal(providerId: string, providerName: string) {
    setSelectedProvider({ id: providerId, name: providerName });
    setKeyInput("");
    setModalOpen(true);
  }

  async function handleStoreKey() {
    if (!selectedProvider) return;
    try {
      await storeKey.mutateAsync({
        providerId: selectedProvider.id,
        apiKey: keyInput,
      });
      notifications.show({
        title: "Key saved",
        message: `API key for ${selectedProvider.name} stored successfully.`,
        color: "green",
      });
      setModalOpen(false);
    } catch (err) {
      notifications.show({
        title: "Error",
        message:
          err instanceof Error ? err.message : "Failed to store API key",
        color: "red",
      });
    }
  }

  async function handleDelete(providerId: string) {
    try {
      await deleteKey.mutateAsync(providerId);
      notifications.show({
        title: "Key deleted",
        message: "API key removed.",
        color: "green",
      });
    } catch {
      notifications.show({
        title: "Error",
        message: "Failed to delete API key",
        color: "red",
      });
    }
    setConfirmDelete(null);
  }

  async function handleValidate(providerId: string) {
    try {
      const result = await validateKey.mutateAsync(providerId);
      notifications.show({
        title: result.is_valid ? "Key is valid" : "Key is invalid",
        message: result.is_valid
          ? "API key validated successfully."
          : "The API key did not pass validation.",
        color: result.is_valid ? "green" : "orange",
      });
    } catch {
      notifications.show({
        title: "Error",
        message: "Validation request failed",
        color: "red",
      });
    }
  }

  if (providersLoading || keysLoading) {
    return <Text c="dimmed">Loading...</Text>;
  }

  return (
    <>
      <Stack gap="md">
        {providers.map((provider) => {
          const key = getKeyForProvider(provider.id);
          return (
            <Paper key={provider.id} p="md" radius="md" withBorder>
              <Group justify="space-between" wrap="wrap">
                <Stack gap={4}>
                  <Text fw={500}>{provider.display_name}</Text>
                  {key ? (
                    <Group gap="xs">
                      <Badge color="green" variant="light">
                        Active
                      </Badge>
                      <Text size="sm" c="dimmed">
                        {key.masked_key}
                      </Text>
                    </Group>
                  ) : (
                    <Badge color="gray" variant="light">
                      Not configured
                    </Badge>
                  )}
                </Stack>
                <Group gap="xs">
                  <Button
                    size="xs"
                    variant="light"
                    onClick={() =>
                      openModal(provider.id, provider.display_name)
                    }
                  >
                    {key ? "Update Key" : "Add Key"}
                  </Button>
                  {key && (
                    <>
                      <Button
                        size="xs"
                        variant="light"
                        color="blue"
                        loading={validateKey.isPending}
                        onClick={() => handleValidate(provider.id)}
                      >
                        Test
                      </Button>
                      {confirmDelete === provider.id ? (
                        <Group gap={4}>
                          <Button
                            size="xs"
                            color="red"
                            loading={deleteKey.isPending}
                            onClick={() => handleDelete(provider.id)}
                          >
                            Confirm
                          </Button>
                          <Button
                            size="xs"
                            variant="subtle"
                            onClick={() => setConfirmDelete(null)}
                          >
                            Cancel
                          </Button>
                        </Group>
                      ) : (
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          onClick={() => setConfirmDelete(provider.id)}
                        >
                          Delete
                        </Button>
                      )}
                    </>
                  )}
                </Group>
              </Group>
            </Paper>
          );
        })}
      </Stack>

      <Modal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        title={`${selectedProvider?.name} API Key`}
      >
        <Stack>
          <TextInput
            label="API Key"
            placeholder="Paste your API key"
            value={keyInput}
            onChange={(e) => setKeyInput(e.currentTarget.value)}
          />
          <Button
            onClick={handleStoreKey}
            loading={storeKey.isPending}
            disabled={!keyInput.trim()}
          >
            Save
          </Button>
        </Stack>
      </Modal>
    </>
  );
}

/* ─── Default Models Tab ─── */

function DefaultModelsTab() {
  const { data: models = [], isLoading: modelsLoading } = useModels();
  const { data: apiKeys = [], isLoading: keysLoading } = useApiKeys();
  const { data: settings, isLoading: settingsLoading } = useUserSettings();
  const updateSettings = useUpdateSettings();

  // Track user edits separately; null = not yet edited by user
  const [editedModelIds, setEditedModelIds] = useState<string[] | null>(null);

  if (modelsLoading || keysLoading || settingsLoading) {
    return <Text c="dimmed">Loading...</Text>;
  }

  const selectedModelIds = editedModelIds ?? settings?.default_model_ids ?? [];

  // Only show models where user has a key for that provider or has OpenRouter key
  const keyProviderIds = new Set(apiKeys.map((k) => k.provider_id));
  const hasOpenRouter = apiKeys.some((k) => k.provider_slug === "openrouter");

  const availableModels = models.filter(
    (m) => keyProviderIds.has(m.provider_id) || hasOpenRouter
  );

  // Group by provider
  const grouped = new Map<string, typeof availableModels>();
  for (const model of availableModels) {
    const key = model.provider_slug;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(model);
  }

  async function handleSave() {
    try {
      await updateSettings.mutateAsync({
        default_model_ids: selectedModelIds,
      });
      notifications.show({
        title: "Saved",
        message: "Default models updated.",
        color: "green",
      });
    } catch {
      notifications.show({
        title: "Error",
        message: "Failed to save default models",
        color: "red",
      });
    }
  }

  if (availableModels.length === 0) {
    return (
      <Text c="dimmed">
        Add an API key first to see available models.
      </Text>
    );
  }

  return (
    <Stack gap="lg">
      {Array.from(grouped.entries()).map(([providerSlug, providerModels]) => (
        <Paper key={providerSlug} p="md" radius="md" withBorder>
          <Text fw={500} mb="sm" tt="capitalize">
            {providerModels[0]?.provider_slug}
          </Text>
          <Checkbox.Group
            value={selectedModelIds}
            onChange={setEditedModelIds}
          >
            <Stack gap="xs">
              {providerModels.map((model) => (
                <Checkbox
                  key={model.id}
                  value={model.id}
                  label={model.display_name}
                />
              ))}
            </Stack>
          </Checkbox.Group>
        </Paper>
      ))}
      <Button onClick={handleSave} loading={updateSettings.isPending}>
        Save Default Models
      </Button>
    </Stack>
  );
}

/* ─── Preferences Tab ─── */

function PreferencesTab() {
  const { data: settings, isLoading } = useUserSettings();
  const { data: models = [], isLoading: modelsLoading } = useModels();
  const updateSettings = useUpdateSettings();

  // Track user edits separately; null = not yet edited by user
  const [editedUntilConsensus, setEditedUntilConsensus] = useState<
    boolean | null
  >(null);
  const [editedMaxRounds, setEditedMaxRounds] = useState<number | null>(null);
  const [editedSummarizerId, setEditedSummarizerId] = useState<string | null>(
    null
  );

  const serverUntilConsensus = settings?.max_rounds === null;
  const serverMaxRounds = settings?.max_rounds ?? 5;

  const untilConsensus = editedUntilConsensus ?? serverUntilConsensus ?? true;
  const maxRounds = editedMaxRounds ?? serverMaxRounds;
  const summarizerId =
    editedSummarizerId ?? settings?.summarizer_model_id ?? null;

  // Build grouped select data for summarizer model dropdown
  const grouped = new Map<string, typeof models>();
  for (const model of models) {
    const key = model.provider_slug;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(model);
  }
  const selectData = Array.from(grouped.entries()).map(
    ([provider, providerModels]) => ({
      group: provider,
      items: providerModels.map((m) => ({
        value: m.id,
        label: m.display_name,
      })),
    })
  );

  async function handleSave() {
    try {
      await updateSettings.mutateAsync({
        max_rounds: untilConsensus ? null : maxRounds,
        summarizer_model_id: summarizerId,
      });
      notifications.show({
        title: "Saved",
        message: "Preferences updated.",
        color: "green",
      });
    } catch {
      notifications.show({
        title: "Error",
        message: "Failed to save preferences",
        color: "red",
      });
    }
  }

  if (isLoading || modelsLoading) {
    return <Text c="dimmed">Loading...</Text>;
  }

  return (
    <Stack gap="md">
      <Switch
        label="Until consensus"
        description="When enabled, rounds continue until all models agree."
        checked={untilConsensus}
        onChange={(e) => setEditedUntilConsensus(e.currentTarget.checked)}
      />
      <NumberInput
        label="Maximum rounds"
        description="Fixed number of discussion rounds (2-20)"
        min={2}
        max={20}
        value={maxRounds}
        onChange={(val) => typeof val === "number" && setEditedMaxRounds(val)}
        disabled={untilConsensus}
      />
      <Select
        label="Summarizer model"
        description="Model used to summarize each round before critique. Defaults to GPT-4o Mini."
        placeholder="GPT-4o Mini (default)"
        data={selectData}
        value={summarizerId}
        onChange={setEditedSummarizerId}
        clearable
        searchable
      />
      <Button onClick={handleSave} loading={updateSettings.isPending}>
        Save Preferences
      </Button>
    </Stack>
  );
}

/* ─── Settings Page ─── */

export default function SettingsPage() {
  return (
    <Container size="md" py="xl">
      <Title order={2} mb="lg">
        Settings
      </Title>
      <Tabs defaultValue="api-keys">
        <Tabs.List>
          <Tabs.Tab value="api-keys">API Keys</Tabs.Tab>
          <Tabs.Tab value="default-models">Default Models</Tabs.Tab>
          <Tabs.Tab value="preferences">Preferences</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="api-keys" pt="md">
          <ApiKeysTab />
        </Tabs.Panel>

        <Tabs.Panel value="default-models" pt="md">
          <DefaultModelsTab />
        </Tabs.Panel>

        <Tabs.Panel value="preferences" pt="md">
          <PreferencesTab />
        </Tabs.Panel>
      </Tabs>
    </Container>
  );
}
