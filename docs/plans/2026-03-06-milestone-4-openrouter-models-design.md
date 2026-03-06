# Milestone 4: OpenRouter Dynamic Models

## Overview

Replace the hardcoded short model list with up-to-date frontier models, add OpenRouter as a first-class provider with curated defaults, and let users search/browse the full OpenRouter catalog to add custom models to their personal list.

## Database Schema

### Normalized three-table design

**`llm_models`** (renamed from current table, now the single source of truth for all model metadata):

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| provider_id | UUID | FK → providers |
| slug | VARCHAR | unique per provider |
| display_name | VARCHAR | |
| model_type | VARCHAR | nullable label: "chat", "reasoning", "hybrid", "code", "diffusion" |
| input_price_per_mtok | NUMERIC | nullable |
| output_price_per_mtok | NUMERIC | nullable |
| context_window | INTEGER | nullable |
| tokens_per_second | FLOAT | nullable |
| is_active | BOOLEAN | default true |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**`default_models`** (curated catalog visible to all users):

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| llm_model_id | UUID | FK → llm_models, unique |
| display_order | INTEGER | for UI sorting |

**`user_custom_models`** (per-user additions from OpenRouter):

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| llm_model_id | UUID | FK → llm_models |
| created_at | TIMESTAMP | |
| **unique** | (user_id, llm_model_id) | |

**`user_default_models`** (unchanged — user's selected models for consensus):

| Column | Type | Notes |
|--------|------|-------|
| user_id | UUID | FK → users |
| llm_model_id | UUID | FK → llm_models |

When a user adds an OpenRouter model, we upsert the metadata into `llm_models` (if it doesn't already exist by slug) and create a `user_custom_models` link. If another user adds the same model later, we reuse the existing `llm_models` row.

## Updated Seed Data

### OpenAI

| Model | Slug | Type | Input $/M | Output $/M | Context |
|-------|------|------|-----------|------------|---------|
| GPT-5 | gpt-5 | chat | 1.25 | 10.00 | 400K |
| GPT-5 Mini | gpt-5-mini | chat | 0.25 | 2.00 | 400K |
| o3 | o3 | reasoning | 2.00 | 8.00 | 200K |
| o4-mini | o4-mini | reasoning | — | — | 200K |

### Anthropic

| Model | Slug | Type | Input $/M | Output $/M | Context |
|-------|------|------|-----------|------------|---------|
| Claude Opus 4.6 | claude-opus-4-6 | hybrid | 5.00 | 25.00 | 1M |
| Claude Sonnet 4.6 | claude-sonnet-4-6 | hybrid | 3.00 | 15.00 | 1M |
| Claude Haiku 4.5 | claude-haiku-4-5 | chat | 0.25 | 1.25 | 200K |

### Google

| Model | Slug | Type | Input $/M | Output $/M | Context |
|-------|------|------|-----------|------------|---------|
| Gemini 3.1 Pro | gemini-3.1-pro | hybrid | 2.00 | 12.00 | 1M |
| Gemini 3.1 Flash Lite | gemini-3.1-flash-lite | chat | 0.25 | 1.50 | 1M |

### Mistral

| Model | Slug | Type | Input $/M | Output $/M | Context |
|-------|------|------|-----------|------------|---------|
| Mistral Large 3 | mistral-large-3 | chat | 0.50 | 1.50 | — |
| Mistral Medium 3 | mistral-medium-3 | chat | 0.40 | 2.00 | — |

### OpenRouter (curated defaults — models not available via other providers)

| Model | Slug | Type | Input $/M | Output $/M | Context |
|-------|------|------|-----------|------------|---------|
| DeepSeek V3.2 | deepseek/deepseek-v3.2 | hybrid | 0.25 | 0.38 | 164K |
| Qwen3 Coder | qwen/qwen3-coder | code | 0.22 | 1.00 | 262K |

## Backend API

### New endpoints

**`GET /api/openrouter/models`** — Search/browse OpenRouter catalog
- Query params: `search` (optional string)
- Uses the authenticated user's stored OpenRouter API key
- Proxies to OpenRouter `GET /api/v1/models`, maps response to our schema
- Returns: list of models with slug, display_name, model_type (inferred from tags, default "chat"), pricing, context_window, tokens_per_second
- 401 if user has no OpenRouter key configured

**`POST /api/users/me/custom-models`** — Add a model from OpenRouter
- Body: `{ model_slug, display_name, model_type?, input_price_per_mtok?, output_price_per_mtok?, context_window?, tokens_per_second? }`
- Upserts into `llm_models` (by slug), creates `user_custom_models` link
- Returns the model

**`DELETE /api/users/me/custom-models/{model_id}`** — Remove a custom model
- Deletes `user_custom_models` link (and any `user_default_models` reference)
- Does NOT delete the `llm_models` row (other users may reference it)

### Updated endpoints

- `GET /api/models` — returns `default_models` join `llm_models`, includes new fields (model_type, tokens_per_second)
- `GET /api/users/me/settings` — default_model_ids can reference any `llm_models` row
- `PUT /api/users/me/settings` — validates model IDs exist in `llm_models`

## Frontend

### Default Models tab (restructured)

1. **Curated models** (top) — grouped by provider, each model shows: name, type badge, pricing, context window, tokens/sec where available. Checkbox selection for consensus defaults.
2. **Divider: "Your custom models"**
3. **Custom models section** — user-added models with a visual badge/flag, same metadata display, remove button, checkbox selection.
4. **"Add from OpenRouter" button** — opens a modal:
   - Requires OpenRouter API key (shows message + link to API Keys tab if not configured)
   - **Search tab**: search input with debounced search-as-you-type, results from OpenRouter API
   - **Browse tab**: full model list grouped by provider, paginated or virtualized for performance
   - Each model row: name, type, pricing, context window, tokens/sec, "Add" button
   - Adding a model closes nothing — user can add multiple, then close modal

## Model Resolution

`model_registry.py` already handles OpenRouter fallback. Update to:
- Query `llm_models` directly (covers both default and custom models)
- Custom OpenRouter models route directly through OpenRouter with their stored slug (no provider prefix needed — slug already includes it, e.g. `deepseek/deepseek-v3.2`)

## Testing

- Alembic migration: table rename, seed data update, new columns
- `GET /api/openrouter/models`: proxy + mapping, missing key handling
- Custom model CRUD: add, remove, duplicate prevention
- Settings: selecting custom models as defaults
- Model registry: resolution with custom models
- Frontend: modal search/browse, add/remove flow, metadata display
