# Twenty CRM — OpenRouter Patch

Patches [Twenty CRM](https://twenty.com) to route AI requests through [OpenRouter](https://openrouter.ai) instead of directly to OpenAI/Anthropic.

## Why

Twenty's self-hosted AI uses `@ai-sdk/openai` which calls OpenAI's Responses API — a newer streaming format OpenRouter doesn't support. This patch switches both the `openai` and `anthropic` providers to `@ai-sdk/openai-compatible`, sets `baseUrl` to OpenRouter, and hardcodes your OpenRouter key (template resolution is unreliable for non-registered config vars).

## Usage

```bash
# 1. Pull the original ai-providers.json from the running container
docker cp twenty-server:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json ./ai-providers.json

# 2. Apply the patch
python3 ai-providers.json.patch.py --key sk-or-v1-YOUR_KEY

# 3. Mount the patched file in docker-compose.yml (both server and worker)
```

In `docker-compose.yml`, add to **both** `twenty-server` and `twenty-worker` services:

```yaml
volumes:
  - ./ai-providers.json:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json:ro
```

Also add to environment of both services:

```yaml
environment:
  OPENAI_API_KEY: sk-or-v1-YOUR_KEY  # must be set for isProviderConfigured() check
```

Then force-recreate both containers:

```bash
docker compose up -d --force-recreate twenty-server twenty-worker
```

## Enable models in the workspace DB

After containers are up, run via the Twenty API (or directly in psql):

```sql
UPDATE core."workspace" SET
  "enabledAiModelIds" = ARRAY['openai/gpt-4o', 'anthropic/claude-sonnet-4.5'],
  "smartModel" = 'anthropic/claude-sonnet-4.5',
  "fastModel" = 'openai/gpt-4o',
  "useRecommendedModels" = false
WHERE id = 'YOUR_WORKSPACE_ID';
```

Also insert the API key into the config table so the LLM registry hash changes and models register:

```sql
INSERT INTO core."keyValuePair" (id, "workspaceId", key, value, type, "createdAt", "updatedAt")
VALUES (gen_random_uuid(), NULL, 'OPENAI_API_KEY', '"sk-or-v1-YOUR_KEY"', 'CONFIG_VARIABLE', NOW(), NOW())
ON CONFLICT DO NOTHING;
```

## OpenRouter settings

Go to [openrouter.ai/settings/privacy](https://openrouter.ai/settings/privacy) and disable all **Zero Data Retention** toggles — ZDR blocks many model endpoints and causes "No endpoints available" errors.

## Models included

| Provider | Model | Use |
|----------|-------|-----|
| OpenAI via OpenRouter | `openai/gpt-4o` | Smart + fallback fast |
| OpenAI via OpenRouter | `openai/gpt-4o-mini` | Fast (lightweight tasks) |
| Anthropic via OpenRouter | `anthropic/claude-sonnet-4.5` | Smart (recommended) |
| Anthropic via OpenRouter | `anthropic/claude-haiku-4.5` | Fast alternative |

## Re-applying after Twenty update

When Twenty updates its Docker image, the container is recreated from the new image — the volume mount persists but the JSON inside may change. Re-run the patch script:

```bash
docker cp twenty-server:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json ./ai-providers.json
python3 ai-providers.json.patch.py --key sk-or-v1-YOUR_KEY
docker compose up -d --force-recreate twenty-server twenty-worker
```

## Tested on

- Twenty v2.37.4
- OpenRouter with `anthropic/claude-sonnet-4.5` and `openai/gpt-4o`
