"use client";

import { useState, useEffect, useRef } from "react";
import {
  Alert,
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

const PROVIDER_ORDER = ["anthropic", "openai", "google", "mistral", "xai", "openrouter"];

/* ─── API Keys Tab ─── */

function ApiKeysTab() {
  const { data: rawProviders = [], isLoading: providersLoading } = useProviders();
  const { data: apiKeys = [], isLoading: keysLoading } = useApiKeys();
  const storeKey = useStoreKey();
  const deleteKey = useDeleteKey();
  const validateKey = useValidateKey();

  const providers = [...rawProviders].sort(
    (a, b) => (PROVIDER_ORDER.indexOf(a.slug) ?? 99) - (PROVIDER_ORDER.indexOf(b.slug) ?? 99),
  );

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

/* ─── Model Label (inline name + metadata) ─── */

function modelTypeBadgeColor(modelType: string): string {
  switch (modelType) {
    case "reasoning":
      return "violet";
    case "hybrid":
      return "blue";
    case "code":
      return "green";
    default:
      return "gray";
  }
}

function ModelLabel({
  name,
  model,
  extra,
}: {
  name: string;
  model: {
    model_type?: string | null;
    input_price_per_mtok: string;
    output_price_per_mtok: string;
    context_window: number;
    tokens_per_second?: number | null;
  };
  extra?: React.ReactNode;
}) {
  return (
    <Group gap="xs" wrap="wrap">
      <Text size="sm" fw={500}>
        {name}
      </Text>
      {extra}
      {model.model_type && (
        <Badge size="xs" variant="light" color={modelTypeBadgeColor(model.model_type)}>
          {model.model_type}
        </Badge>
      )}
      <Text size="xs" c="dimmed">
        ${parseFloat(model.input_price_per_mtok).toFixed(2)}/${parseFloat(model.output_price_per_mtok).toFixed(2)} per M tokens
      </Text>
      <Text size="xs" c="dimmed">
        {model.context_window >= 1000000
          ? `${(model.context_window / 1000000).toFixed(model.context_window % 1000000 === 0 ? 0 : 1)}M context`
          : `${(model.context_window / 1000).toFixed(0)}K context`}
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
  excludedSlugs,
}: {
  opened: boolean;
  onClose: () => void;
  hasOpenRouterKey: boolean;
  excludedSlugs: Set<string>;
}) {
  const [searchInput, setSearchInput] = useState("");
  const addCustomModel = useAddCustomModel();

  const {
    data: allModels = [],
    isLoading,
  } = useOpenRouterModels(opened && hasOpenRouterKey);

  const filtered = searchInput.trim()
    ? allModels.filter((m) => {
        const term = searchInput.toLowerCase();
        return m.display_name.toLowerCase().includes(term) || m.slug.toLowerCase().includes(term);
      })
    : allModels;

  function handleClose() {
    setSearchInput("");
    onClose();
  }

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
          placeholder="Search models..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.currentTarget.value)}
        />

        {isLoading && (
          <Group justify="center" py="md">
            <Loader size="sm" />
          </Group>
        )}

        {!isLoading && filtered.length === 0 && (
          <Text c="dimmed" ta="center" py="md">
            No models found.
          </Text>
        )}

        {filtered.length > 0 && (
          <ScrollArea.Autosize mah={400}>
            <Stack gap="xs">
              {filtered.map((model) => {
                const alreadyAdded = excludedSlugs.has(model.slug);
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
                                ${parseFloat(model.input_price_per_mtok).toFixed(2)}/$
                                {parseFloat(model.output_price_per_mtok).toFixed(2)} per M tokens
                              </Text>
                            )}
                          {model.context_window && (
                            <Text size="xs" c="dimmed">
                              {model.context_window >= 1000000
                                ? `${(model.context_window / 1000000).toFixed(model.context_window % 1000000 === 0 ? 0 : 1)}M context`
                                : `${(model.context_window / 1000).toFixed(0)}K context`}
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
  const { data: providers = [] } = useProviders();
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

  // Group by provider, sorted in preferred order
  const providerOrder = PROVIDER_ORDER;
  const grouped = new Map<string, typeof availableModels>();
  for (const slug of providerOrder) {
    const providerModels = availableModels.filter((m) => m.provider_slug === slug);
    if (providerModels.length > 0) grouped.set(slug, providerModels);
  }
  // Append any providers not in the list
  for (const model of availableModels) {
    if (!grouped.has(model.provider_slug)) {
      grouped.set(model.provider_slug, []);
    }
    if (!providerOrder.includes(model.provider_slug)) {
      grouped.get(model.provider_slug)!.push(model);
    }
  }

  const excludedSlugs = new Set([
    ...models.map((m) => m.slug),
    ...customModels.map((m) => m.slug),
  ]);

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
      <Alert variant="light" color="blue" title="How it works">
        Select the models that will be used by default for every new inquiry.
        You can always override these on a per-inquiry basis.
      </Alert>

      {/* Curated models grouped by provider */}
      {Array.from(grouped.entries()).map(([providerSlug, providerModels]) => (
        <Paper key={providerSlug} p="md" radius="md" withBorder>
          <Text fw={500} mb="sm">
            {providers.find((p) => p.slug === providerSlug)?.display_name ?? providerSlug}
          </Text>
          <Stack gap="xs">
            {providerModels.map((model) => (
              <Checkbox
                key={model.id}
                checked={selectedModelIds.includes(model.id)}
                onChange={() => toggleModelId(model.id)}
                label={<ModelLabel name={model.display_name} model={model} />}
              />
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
                  <Checkbox
                    checked={selectedModelIds.includes(model.id)}
                    onChange={() => toggleModelId(model.id)}
                    label={
                      <ModelLabel
                        name={model.display_name}
                        model={model}
                        extra={
                          <Badge size="xs" variant="outline" color="teal">
                            Custom
                          </Badge>
                        }
                      />
                    }
                    style={{ flex: 1 }}
                  />
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

      <Group>
        <Button onClick={handleSave} loading={updateSettings.isPending}>
          Save
        </Button>
        <Button
          variant="light"
          onClick={() => setOpenRouterModalOpen(true)}
        >
          Add from OpenRouter
        </Button>
      </Group>

      <AddFromOpenRouterModal
        opened={openRouterModalOpen}
        onClose={() => setOpenRouterModalOpen(false)}
        hasOpenRouterKey={hasOpenRouter}
        excludedSlugs={excludedSlugs}
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
