# Enquiry Model Selection UX

## Problem

When creating a new enquiry, the system does not pre-select the default models configured in user preferences. The model selection UI uses plain checkboxes, which is cluttered.

## Design

### Enquiry Input

- Replace `Textarea` + standalone "Start Consensus" button with a rounded `Textarea` (`radius="xl"`) that auto-grows via `field-sizing: content` CSS.
- Right section contains an `ActionIcon` (arrow icon) to submit, disabled when form is invalid (< 2 models or empty enquiry).
- Cmd/Ctrl+Enter keyboard shortcut still works.

### Model Selection

- Selected models shown as `Pill` components with close (x) buttons.
- Close button disabled when exactly 2 models remain.
- An "Add model" button at the end of the pills row opens a `Popover`.
- Popover contains a scrollable list of all available models grouped by provider (uppercase label), with a checkmark icon on selected ones.
- Clicking a model in the popover toggles its selection.

### Pre-fill from Preferences

- Fetch user settings via `useUserSettings()` on mount.
- Initialize `selectedModelIds` from `default_model_ids`, filtered against available models (in case a default model's API key was removed).
- Initialize `untilConsensus` from `settings.max_rounds === null`.
- Initialize `maxRounds` from `settings.max_rounds ?? 5`.

### Scope

- All changes in `frontend/src/app/(protected)/sessions/new/page.tsx`.
- No new files. No backend changes.
- Reuse existing `useUserSettings` and `useModels` hooks from `@/lib/hooks`.
