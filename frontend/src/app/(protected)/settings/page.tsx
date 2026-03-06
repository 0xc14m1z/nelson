"use client";

import { useState, useEffect, useRef } from "react";
import {
  Badge,
  Button,
  Checkbox,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  ScrollArea,
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
  useCustomModels,
  useAddCustomModel,
  useDeleteCustomModel,
  useOpenRouterModels,
} from "../../../lib/hooks";
import type { CustomModel, OpenRouterModel } from "../../../lib/hooks";

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

/* ─── Model Metadata ─── */

function ModelMetadata({
  model,
}: {
  model: {
    model_type?: string | null;
    input_price_per_mtok: string;
    output_price_per_mtok: string;
    context_window: number;
    tokens_per_second?: number | null;
  };
}) {
  return (
    <Group gap="xs" mt={4}>
      {model.model_type && (
        <Badge
          size="xs"
          variant="light"
          color={
            model.model_type === "reasoning"
              ? "violet"
              : model.model_type === "hybrid"
                ? "blue"
                : model.model_type === "code"
                  ? "green"
                  : "gray"
          }
        >
          {model.model_type}
        </Badge>
      )}
      <Text size="xs" c="dimmed">
        ${model.input_price_per_mtok}/${model.output_price_per_mtok} per M
        tokens
      </Text>
      <Text size="xs" c="dimmed">
        {(model.context_window / 1000).toFixed(0)}K ctx
      </Text>
      {model.tokens_per_second && (
        <Text size="xs" c="dimmed">
          {model.tokens_per_second} tok/s
        </Text>
      )}
    </Group>
  );
}

/* ─── Add from OpenRouter Modal ─── */

function AddFromOpenRouterModal({
  opened,
  onClose,
  hasOpenRouterKey,
  customModelSlugs,
}: {
  opened: boolean;
  onClose: () => void;
  hasOpenRouterKey: boolean;
  customModelSlugs: Set<string>;
}) {
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const addCustomModel = useAddCustomModel();

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(searchInput);
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [searchInput]);

  function handleClose() {
    setSearchInput("");
    setDebouncedSearch("");
    onClose();
  }

  const {
    data: results = [],
    isLoading,
    isFetching,
  } = useOpenRouterModels(debouncedSearch);

  async function handleAdd(model: OpenRouterModel) {
    try {
      await addCustomModel.mutateAsync({
        model_slug: model.slug,
        display_name: model.display_name,
        model_type: model.model_type,
        input_price_per_mtok: model.input_price_per_mtok
          ? parseFloat(model.input_price_per_mtok)
          : null,
        output_price_per_mtok: model.output_price_per_mtok
          ? parseFloat(model.output_price_per_mtok)
          : null,
        context_window: model.context_window,
        tokens_per_second: model.tokens_per_second,
      });
      notifications.show({
        title: "Model added",
        message: `${model.display_name} added to your custom models.`,
        color: "green",
      });
    } catch (err) {
      notifications.show({
        title: "Error",
        message:
          err instanceof Error ? err.message : "Failed to add custom model",
        color: "red",
      });
    }
  }

  if (!hasOpenRouterKey) {
    return (
      <Modal opened={opened} onClose={handleClose} title="Add from OpenRouter">
        <Text c="dimmed">
          Add an OpenRouter API key first to browse available models.
        </Text>
      </Modal>
    );
  }

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title="Add from OpenRouter"
      size="lg"
    >
      <Stack>
        <TextInput
          placeholder="Search models (min 2 characters)..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.currentTarget.value)}
        />

        {(isLoading || isFetching) && debouncedSearch.length >= 2 && (
          <Group justify="center" py="md">
            <Loader size="sm" />
          </Group>
        )}

        {debouncedSearch.length >= 2 &&
          !isLoading &&
          !isFetching &&
          results.length === 0 && (
            <Text c="dimmed" ta="center" py="md">
              No models found.
            </Text>
          )}

        {results.length > 0 && (
          <ScrollArea.Autosize mah={400}>
            <Stack gap="xs">
              {results.map((model) => {
                const alreadyAdded = customModelSlugs.has(model.slug);
                return (
                  <Paper key={model.slug} p="sm" radius="sm" withBorder>
                    <Group justify="space-between" wrap="wrap">
                      <Stack gap={2} style={{ flex: 1 }}>
                        <Text size="sm" fw={500}>
                          {model.display_name}
                        </Text>
                        <Group gap="xs">
                          {model.model_type && (
                            <Badge
                              size="xs"
                              variant="light"
                              color={
                                model.model_type === "reasoning"
                                  ? "violet"
                                  : model.model_type === "hybrid"
                                    ? "blue"
                                    : model.model_type === "code"
                                      ? "green"
                                      : "gray"
                              }
                            >
                              {model.model_type}
                            </Badge>
                          )}
                          {model.input_price_per_mtok &&
                            model.output_price_per_mtok && (
                              <Text size="xs" c="dimmed">
                                ${model.input_price_per_mtok}/$
                                {model.output_price_per_mtok} per M tokens
                              </Text>
                            )}
                          {model.context_window && (
                            <Text size="xs" c="dimmed">
                              {(model.context_window / 1000).toFixed(0)}K ctx
                            </Text>
                          )}
                        </Group>
                      </Stack>
                      <Button
                        size="xs"
                        variant="light"
                        disabled={alreadyAdded || addCustomModel.isPending}
                        onClick={() => handleAdd(model)}
                      >
                        {alreadyAdded ? "Added" : "Add"}
                      </Button>
                    </Group>
                  </Paper>
                );
              })}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Modal>
  );
}

/* ─── Default Models Tab ─── */

function DefaultModelsTab() {
  const { data: models = [], isLoading: modelsLoading } = useModels();
  const { data: apiKeys = [], isLoading: keysLoading } = useApiKeys();
  const { data: settings, isLoading: settingsLoading } = useUserSettings();
  const { data: customModels = [], isLoading: customModelsLoading } =
    useCustomModels();
  const deleteCustomModel = useDeleteCustomModel();
  const updateSettings = useUpdateSettings();

  const [openRouterModalOpen, setOpenRouterModalOpen] = useState(false);

  // Track user edits separately; null = not yet edited by user
  const [editedModelIds, setEditedModelIds] = useState<string[] | null>(null);

  if (modelsLoading || keysLoading || settingsLoading || customModelsLoading) {
    return <Text c="dimmed">Loading...</Text>;
  }

  const selectedModelIds = editedModelIds ?? settings?.default_model_ids ?? [];

  // Only show models where user has a key for that provider or has OpenRouter key
  const keyProviderIds = new Set(apiKeys.map((k) => k.provider_id));
  const hasOpenRouter = apiKeys.some((k) => k.provider_slug === "openrouter");

  const availableModels = models.filter(
    (m) => keyProviderIds.has(m.provider_id) || hasOpenRouter,
  );

  // Group by provider
  const grouped = new Map<string, typeof availableModels>();
  for (const model of availableModels) {
    const key = model.provider_slug;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(model);
  }

  const customModelSlugs = new Set(customModels.map((m) => m.slug));

  function toggleModelId(modelId: string) {
    const current = editedModelIds ?? settings?.default_model_ids ?? [];
    if (current.includes(modelId)) {
      setEditedModelIds(current.filter((id) => id !== modelId));
    } else {
      setEditedModelIds([...current, modelId]);
    }
  }

  async function handleDeleteCustomModel(model: CustomModel) {
    try {
      // Remove from selection if selected
      const current = editedModelIds ?? settings?.default_model_ids ?? [];
      if (current.includes(model.id)) {
        setEditedModelIds(current.filter((id) => id !== model.id));
      }
      await deleteCustomModel.mutateAsync(model.id);
      notifications.show({
        title: "Model removed",
        message: `${model.display_name} removed from custom models.`,
        color: "green",
      });
    } catch {
      notifications.show({
        title: "Error",
        message: "Failed to remove custom model",
        color: "red",
      });
    }
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

  if (availableModels.length === 0 && customModels.length === 0) {
    return (
      <Text c="dimmed">
        Add an API key first to see available models.
      </Text>
    );
  }

  return (
    <Stack gap="lg">
      {/* Curated models grouped by provider */}
      {Array.from(grouped.entries()).map(([providerSlug, providerModels]) => (
        <Paper key={providerSlug} p="md" radius="md" withBorder>
          <Text fw={500} mb="sm" tt="capitalize">
            {providerModels[0]?.provider_slug}
          </Text>
          <Stack gap="xs">
            {providerModels.map((model) => (
              <div key={model.id}>
                <Checkbox
                  checked={selectedModelIds.includes(model.id)}
                  onChange={() => toggleModelId(model.id)}
                  label={model.display_name}
                />
                <ModelMetadata model={model} />
              </div>
            ))}
          </Stack>
        </Paper>
      ))}

      {/* Custom models section */}
      {customModels.length > 0 && (
        <>
          <Divider label="Your custom models" labelPosition="center" />
          <Paper p="md" radius="md" withBorder>
            <Stack gap="xs">
              {customModels.map((model) => (
                <Group key={model.id} justify="space-between" wrap="wrap">
                  <Stack gap={0} style={{ flex: 1 }}>
                    <Group gap="xs">
                      <Checkbox
                        checked={selectedModelIds.includes(model.id)}
                        onChange={() => toggleModelId(model.id)}
                        label={model.display_name}
                      />
                      <Badge size="xs" variant="outline" color="teal">
                        Custom
                      </Badge>
                    </Group>
                    <ModelMetadata model={model} />
                  </Stack>
                  <Button
                    size="xs"
                    variant="subtle"
                    color="red"
                    onClick={() => handleDeleteCustomModel(model)}
                    loading={deleteCustomModel.isPending}
                  >
                    Remove
                  </Button>
                </Group>
              ))}
            </Stack>
          </Paper>
        </>
      )}

      {/* Add from OpenRouter button */}
      <Button
        variant="light"
        onClick={() => setOpenRouterModalOpen(true)}
      >
        Add from OpenRouter
      </Button>

      <Button onClick={handleSave} loading={updateSettings.isPending}>
        Save Default Models
      </Button>

      <AddFromOpenRouterModal
        opened={openRouterModalOpen}
        onClose={() => setOpenRouterModalOpen(false)}
        hasOpenRouterKey={hasOpenRouter}
        customModelSlugs={customModelSlugs}
      />
    </Stack>
  );
}

/* ─── Preferences Tab ─── */

function PreferencesTab() {
  const { data: settings, isLoading } = useUserSettings();
  const updateSettings = useUpdateSettings();

  // Track user edits separately; null = not yet edited by user
  const [editedUntilConsensus, setEditedUntilConsensus] = useState<
    boolean | null
  >(null);
  const [editedMaxRounds, setEditedMaxRounds] = useState<number | null>(null);

  const serverUntilConsensus = settings?.max_rounds === null;
  const serverMaxRounds = settings?.max_rounds ?? 5;

  const untilConsensus = editedUntilConsensus ?? serverUntilConsensus ?? true;
  const maxRounds = editedMaxRounds ?? serverMaxRounds;

  async function handleSave() {
    try {
      await updateSettings.mutateAsync({
        max_rounds: untilConsensus ? null : maxRounds,
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

  if (isLoading) {
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
