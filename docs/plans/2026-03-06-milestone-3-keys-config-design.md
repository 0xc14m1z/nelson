# Milestone 3 — API Keys + Model Config Design

## Overview

Enable users to store encrypted API keys, browse providers/models, configure default models and round preferences, and resolve which key to use for a given model.

## Task 3.1 — API Keys Backend

### Database

New `api_keys` table (migration required):

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | FK users | |
| provider_id | FK providers | |
| encrypted_key | BYTEA | Fernet-encrypted |
| is_valid | BOOL | Set during validation |
| validated_at | TIMESTAMP | Last validation time |
| created_at | TIMESTAMP | |

UNIQUE(`user_id`, `provider_id`) — one key per provider per user.

### Encryption

`keys/encryption.py`: `encrypt_api_key(key: str) -> bytes` and `decrypt_api_key(encrypted: bytes) -> str`. Uses `Fernet(settings.fernet_key)` from the `cryptography` library (already a dependency).

### Key Validation

Validate by calling each provider's list-models endpoint (lightweight, read-only, universally available):

| Provider | Endpoint | Auth |
|----------|----------|------|
| openai | `GET /v1/models` | `Authorization: Bearer {key}` |
| anthropic | `GET /v1/models` | `x-api-key: {key}`, `anthropic-version: 2023-06-01` |
| google | `GET /v1beta/models?key={key}` | Query param |
| mistral | `GET /v1/models` | `Authorization: Bearer {key}` |
| openrouter | `GET /api/v1/models` | `Authorization: Bearer {key}` |

Uses `httpx.AsyncClient` with 10s timeout. Returns `(is_valid: bool, error: str | None)`.

### Service

`keys/service.py`:
- `store_key(user_id, provider_id, raw_key)` — validate, encrypt, upsert (update if exists)
- `list_keys(user_id)` — return list with masked display (`****{last4}`)
- `delete_key(user_id, provider_id)` — remove key
- `validate_existing_key(user_id, provider_id)` — decrypt stored key, re-validate
- `get_decrypted_key(user_id, provider_id)` — for model registry (internal use)

### Router

`keys/router.py`:
- `GET /api/keys` — list user's keys (masked, never returns raw keys)
- `POST /api/keys` — `{ provider_id, api_key }` — validates then stores. Rejects invalid keys.
- `DELETE /api/keys/{provider_id}` — remove key
- `POST /api/keys/{provider_id}/validate` — test existing stored key

All endpoints require auth (`get_current_user` dependency).

### Tests

- Encrypt/decrypt roundtrip
- Store + retrieve masked key
- Validation calls correct provider endpoint (real HTTP where possible)
- Duplicate key per provider upserts (not errors)
- Delete removes key
- Unauthorized access rejected

## Task 3.2 — Providers, Models, and User Settings

### Catalog Endpoints

`catalog/router.py` (read-only reference data):
- `GET /api/providers` — list all active providers
- `GET /api/models?provider_id=` — list all active models, optionally filtered

### User Endpoints

`users/router.py`:
- `GET /api/users/me` — user profile (id, email, display_name, billing_mode)
- `PUT /api/users/me` — update display_name, billing_mode
- `GET /api/users/me/settings` — user settings + default model IDs
- `PUT /api/users/me/settings` — `{ max_rounds: int | null, default_model_ids: UUID[] }`

### New Migration

`user_default_models` join table:
- `user_id` FK users
- `llm_model_id` FK llm_models
- Composite PK(`user_id`, `llm_model_id`)

### Settings Sync Logic

`PUT /api/users/me/settings`:
1. Upsert `user_settings` row (create if not exists)
2. Sync `user_default_models`: delete all for user, re-insert new set
3. Validate all model IDs exist and are active

### Tests

- Providers list matches seed data (5 providers)
- Models list returns 11 models, filterable by provider
- Settings round-trip (write then read back)
- Default models sync correctly
- Invalid model IDs rejected
- `/auth/me` remains unchanged (backward compat)

## Task 3.3 — Model Registry

### Scope

Key resolution logic only. PydanticAI model instantiation deferred to Milestone 4.

### Interface

`agent/model_registry.py`:

```python
@dataclass
class ResolvedModel:
    api_key: str          # decrypted key
    base_url: str         # provider's base URL
    model_slug: str       # slug to send to the API
    provider_slug: str    # for logging/tracking
    via_openrouter: bool  # True if using OpenRouter fallback
```

`resolve_model(user_id, llm_model, db) -> ResolvedModel`

### Resolution Order

1. User's own key for the model's provider → use provider `base_url`, model `slug`
2. User's OpenRouter key → use OpenRouter `base_url`, slug becomes `{provider_slug}/{model_slug}`
3. Raise `NoKeyAvailableError`

Exception: if the model's provider IS OpenRouter, only step 1 applies (no slug translation).

### Tests

- Resolves with direct key
- Falls back to OpenRouter with correct slug translation
- OpenRouter-native models don't get slug prefix
- Raises error when no key available

## Task 3.4 — Settings Frontend

### Page Structure

`/(protected)/settings/page.tsx` — Mantine `Tabs` with three tabs.

### Tab 1: API Keys

- List all 5 providers with key status (stored/not stored, valid/invalid badge)
- For each: masked key (`****{last4}`), "Add/Update" opens modal, "Test" button, "Delete" with confirm
- `@mantine/notifications` for feedback

### Tab 2: Default Models

- Multi-select from available models grouped by provider
- Only show models where user has a key for that provider (or OpenRouter key)
- Mantine `Checkbox.Group` or `MultiSelect`
- Save button → `PUT /api/users/me/settings`

### Tab 3: Preferences

- Round mode toggle: "Until consensus" (null) vs. specific count (NumberInput, range 2-20)
- Save → `PUT /api/users/me/settings`

### Data Fetching

TanStack Query hooks:
- `useProviders()`, `useModels()`, `useApiKeys()`, `useUserSettings()`
- Mutations for key CRUD and settings update

### Navigation

Add "Settings" link to the protected layout sidebar/nav.

### Tests

- Forms render with correct provider list
- Key masking displays correctly
- Model selector filters by available keys
- Settings save and reload

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Key validation method | List models endpoint | Lightweight, read-only, universal |
| Settings page scope | All 3 tabs in one milestone | Matches PLAN.md, ships complete feature |
| Default models endpoint | Part of settings payload | Simpler — one PUT manages all prefs |
| Model registry scope | Key resolution only | PydanticAI integration deferred to M4 |
| Catalog router name | `catalog/` | Read-only reference data, not user-owned |
