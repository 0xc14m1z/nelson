# Enquiry Model Selection UX — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Pre-select default models from user preferences on the new enquiry page and replace checkbox-based model selection with a tags + popover UI.

**Architecture:** Single-file frontend change to `sessions/new/page.tsx`. Fetch user settings via existing `useUserSettings()` hook, use `useEffect` to initialize state once both settings and models load. Replace `Checkbox.Group` with `Pill` tags + `Popover` dropdown. Replace `Textarea` + `Button` with a rounded auto-growing `Textarea` with embedded `ActionIcon`.

**Tech Stack:** React, Mantine 8 (Pill, Popover, ActionIcon, Textarea, ScrollArea), @tabler/icons-react, @tanstack/react-query

---

### Task 1: Pre-fill form state from user preferences

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/page.tsx`

**Step 1: Add useUserSettings import and call**

Add to imports:
```tsx
import { useEffect } from "react";
import { useUserSettings } from "@/lib/hooks";
import type { Model as FullModel } from "@/lib/hooks";
```

Replace the local `Model` interface with the imported `FullModel` type (alias as `Model` in the import or just use it directly). The local interface is a subset — the hook's `Model` type has all the fields we need.

Inside the component, add:
```tsx
const { data: settings } = useUserSettings();
```

**Step 2: Use useEffect to initialize state from settings**

Add after the queries:
```tsx
const [initialized, setInitialized] = useState(false);

useEffect(() => {
  if (initialized || !settings || models.length === 0) return;

  // Filter default models to only those available (user still has API keys)
  const availableIds = new Set(models.map((m) => m.id));
  const validDefaults = settings.default_model_ids.filter((id) => availableIds.has(id));
  if (validDefaults.length > 0) setSelectedModelIds(validDefaults);

  // Pre-fill consensus settings
  setUntilConsensus(settings.max_rounds === null);
  if (settings.max_rounds !== null) setMaxRounds(settings.max_rounds);

  setInitialized(true);
}, [initialized, settings, models]);
```

**Step 3: Run existing tests to verify no regression**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun test sessions/new`
Expected: All 3 existing tests pass (the mock returns no settings so defaults stay as-is).

**Step 4: Commit**

```bash
git add frontend/src/app/\(protected\)/sessions/new/page.tsx
git commit -m "feat: pre-fill enquiry form from user preferences"
```

---

### Task 2: Replace model selection with Pill tags + Popover

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/page.tsx`

**Step 1: Add new Mantine imports**

Replace the Mantine imports with:
```tsx
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
  Title,
  UnstyledButton,
} from "@mantine/core";
import { IconCheck, IconPlus } from "@tabler/icons-react";
```

Remove `Button` and `Checkbox` from imports (no longer used).

**Step 2: Add toggle helper**

Inside the component, add:
```tsx
const toggleModel = (id: string) => {
  setSelectedModelIds((prev) =>
    prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
  );
};
```

**Step 3: Replace the model selection JSX**

Replace the `<Box>` containing `Checkbox.Group` sections (lines 95-109) with:

```tsx
<Box>
  <Text fw={500} mb="xs">Models</Text>
  <Group gap="xs">
    {selectedModelIds
      .map((id) => models.find((m) => m.id === id))
      .filter(Boolean)
      .map((m) => (
        <Pill
          key={m!.id}
          withRemoveButton
          onRemove={() => toggleModel(m!.id)}
          removeButtonProps={{
            disabled: selectedModelIds.length <= 2,
          }}
        >
          {m!.display_name}
        </Pill>
      ))}
    <Popover width={300} position="bottom-start" shadow="md">
      <Popover.Target>
        <ActionIcon variant="subtle" size="sm">
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
                    onClick={() => toggleModel(m.id)}
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
```

**Step 4: Run tests**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun test sessions/new`
Expected: Some tests will fail because assertions reference removed elements ("Select models (minimum 2)", "Start Consensus", checkboxes). We'll fix those in Task 4.

**Step 5: Commit**

```bash
git add frontend/src/app/\(protected\)/sessions/new/page.tsx
git commit -m "feat: replace model checkboxes with pill tags and popover"
```

---

### Task 3: Replace Textarea + Button with rounded auto-growing input

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/page.tsx`

**Step 1: Add IconArrowRight import**

Add to tabler imports:
```tsx
import { IconArrowRight, IconCheck, IconPlus } from "@tabler/icons-react";
```

**Step 2: Replace the Textarea and Button**

Remove the `<Title>`, `<Textarea>`, and `<Button>` elements. Replace with:

```tsx
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
```

Note: `field-sizing: content` is set via Mantine's `styles` prop on the input element. The `as never` cast is needed because Mantine's types don't include `fieldSizing` yet (it's a newer CSS property).

Also remove `autosize` and `minRows` since `field-sizing: content` handles auto-growth natively.

**Step 3: Remove the standalone Button**

Delete the `<Button onClick={...}>Start Consensus</Button>` block entirely (it's replaced by the ActionIcon in the textarea).

**Step 4: Run dev server and visually verify**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun dev`
Check `http://localhost:3000/sessions/new` — textarea should be rounded, auto-grow on input, and have the arrow button inside.

**Step 5: Commit**

```bash
git add frontend/src/app/\(protected\)/sessions/new/page.tsx
git commit -m "feat: replace textarea and button with rounded input-with-button"
```

---

### Task 4: Update tests for new UI

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/new/__tests__/page.test.tsx`

**Step 1: Update Mantine mock to include new components**

Add to the Mantine mock factory:
- `Pill`: render children + a remove button if `withRemoveButton` is true
- `Popover`, `Popover.Target`, `Popover.Dropdown`: simple wrappers
- `ScrollArea`, `ScrollArea.Autosize`: simple wrapper
- `UnstyledButton`: button element
- `ActionIcon`: button element

Remove `Checkbox` and `Button` from the mock.

Updated mock:
```tsx
vi.mock("@mantine/core", () => {
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  const Pill = (props: Record<string, unknown>) =>
    R.createElement("span", null,
      props.children,
      props.withRemoveButton && R.createElement("button", {
        "aria-label": "Remove",
        onClick: props.onRemove as () => void,
        disabled: (props.removeButtonProps as Record<string, unknown>)?.disabled,
      }, "×"),
    );
  const Popover = Object.assign(wrap(), {
    Target: wrap(),
    Dropdown: wrap(),
  });
  const ScrollArea = Object.assign(wrap(), { Autosize: wrap() });
  return {
    ActionIcon: (props: Record<string, unknown>) =>
      R.createElement("button", {
        "aria-label": props["aria-label"],
        disabled: props.disabled,
        onClick: props.onClick as () => void,
      }, props.children),
    Box: wrap(),
    Group: wrap(),
    NumberInput: wrap(),
    MantineProvider: wrap(),
    Pill,
    Popover,
    ScrollArea,
    Stack: wrap(),
    Switch: (props: Record<string, unknown>) =>
      R.createElement("label", null, R.createElement("input", { type: "checkbox" }), props.label),
    Text: wrap(),
    Textarea: (props: Record<string, unknown>) =>
      R.createElement("textarea", {
        placeholder: props.placeholder as string,
        "aria-label": props["aria-label"] || "enquiry",
      }),
    Title: (props: Record<string, unknown>) =>
      R.createElement(`h${props.order || 1}`, null, props.children),
    UnstyledButton: (props: Record<string, unknown>) =>
      R.createElement("button", { onClick: props.onClick as () => void }, props.children),
  };
});
```

Also add a mock for `@tabler/icons-react`:
```tsx
vi.mock("@tabler/icons-react", () => {
  const R = require("react");
  const icon = () => () => R.createElement("span");
  return { IconArrowRight: icon(), IconCheck: icon(), IconPlus: icon() };
});
```

**Step 2: Add mock for useUserSettings**

Add a `mockSettings` to vi.hoisted:
```tsx
const { mockModels, mockMutateFn, mockSettings } = vi.hoisted(() => ({
  mockModels: [
    { id: "m1", slug: "gpt-4o", display_name: "GPT-4o", provider_slug: "openai" },
    { id: "m2", slug: "claude-3", display_name: "Claude 3", provider_slug: "anthropic" },
    { id: "m3", slug: "gpt-4o-mini", display_name: "GPT-4o Mini", provider_slug: "openai" },
  ],
  mockMutateFn: vi.fn(),
  mockSettings: {
    default_model_ids: ["m1", "m2"],
    max_rounds: null,
    summarizer_model_id: null,
  },
}));
```

Mock `@/lib/hooks`:
```tsx
vi.mock("@/lib/hooks", () => ({
  useUserSettings: () => ({ data: mockSettings, isLoading: false }),
}));
```

**Step 3: Rewrite tests**

```tsx
describe("New Session Page", () => {
  it("renders enquiry textarea with submit button", () => {
    renderPage();
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument();
    expect(screen.getByLabelText("Start consensus")).toBeInTheDocument();
  });

  it("pre-selects default models from user settings", () => {
    renderPage();
    expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    expect(screen.getByText("Claude 3")).toBeInTheDocument();
  });

  it("shows all models in popover grouped by provider", () => {
    renderPage();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("anthropic")).toBeInTheDocument();
    expect(screen.getByText("GPT-4o Mini")).toBeInTheDocument();
  });

  it("disables submit when enquiry is empty", () => {
    renderPage();
    const submit = screen.getByLabelText("Start consensus");
    expect(submit).toBeDisabled();
  });
});
```

**Step 4: Run tests**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun test sessions/new`
Expected: All 4 tests pass.

**Step 5: Commit**

```bash
git add frontend/src/app/\(protected\)/sessions/new/__tests__/page.test.tsx
git commit -m "test: update new session page tests for pill+popover UI"
```

---

### Task 5: Final verification

**Step 1: Run full frontend test suite**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun test`
Expected: All tests pass.

**Step 2: Run lint**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun lint`
Expected: No errors.

**Step 3: Visual check**

Run: `cd /Users/morgandam/Documents/repos/nelson/frontend && bun dev`
Verify at `http://localhost:3000/sessions/new`:
- Default models appear as pills on load
- Close button disabled when 2 models remain
- Add button opens popover with grouped models and checkmarks
- Textarea is rounded, auto-grows, has arrow submit button
- Consensus settings pre-filled from preferences
- Submitting works and redirects to session page
