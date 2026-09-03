# Twenty CRM — OpenRouter Patch

Patches [Twenty CRM](https://twenty.com) self-hosted to route AI requests through [OpenRouter](https://openrouter.ai) with a curated two-tier model list.

## Model tiers

### Frontier
Best-in-class for complex agentic tasks — due diligence, multi-step reasoning, document analysis, long-context workflows. Worth the cost for high-value opportunities.

| Model | Cost (in/out per M) | Context | Vision |
|---|---|---|---|
| Claude Sonnet 4.5 ★ | $3 / $15 | 200k | ✓ |
| Claude Opus 4.5 | $5 / $25 | 200k | ✓ |
| GPT-4o ★ | $2.50 / $10 | 128k | ✓ |
| GPT-4.1 | $2 / $8 | 1M | ✓ |
| o3 (reasoning) | $2 / $8 | 200k | ✓ |
| o4-mini (reasoning) | $1.10 / $4.40 | 200k | ✓ |
| Gemini 2.5 Pro | $1.25 / $10 | 1M | ✓ |
| DeepSeek R1 (reasoning) | $0.50 / $2.19 | 163k | ✗ |
| Grok 3 | $3 / $15 | 131k | ✗ |

### Recommended
Strong everyday models at sensible cost — CRM automation, email drafting, contact enrichment, title generation.

| Model | Cost (in/out per M) | Context | Vision |
|---|---|---|---|
| Claude Haiku 4.5 (fast) | $0.80 / $4 | 200k | ✓ |
| GPT-4o Mini (fast) | $0.15 / $0.60 | 128k | ✓ |
| GPT-4.1 Mini | $0.40 / $1.60 | 1M | ✓ |
| Gemini 2.5 Flash (fast) | $0.30 / $2.50 | 1M | ✓ |
| DeepSeek V3.1 (value) | $0.25 / $1.10 | 163k | ✗ |
| Llama 3.3 70B (open) | $0.10 / $0.40 | 131k | ✗ |
| Mistral Medium 3.1 | $0.40 / $2 | 131k | ✓ |

## Why this patch exists

- Twenty's built-in `@ai-sdk/openai` uses the Responses API — OpenRouter doesn't support it
- Custom `baseUrl` requires switching to `@ai-sdk/openai-compatible`
- Twenty's provider registry needs models pre-registered in `ai-providers.json`

## Usage

```bash
# 1. Pull original JSON from running container (reference only — not modified)
docker cp twenty-server:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json ./ai-providers-orig.json

# 2. Generate patched JSON
python3 patch.py --input ai-providers-orig.json --output ai-providers.json --key sk-or-v1-YOUR_KEY

# 3. Mount in docker-compose.yml — BOTH twenty-server AND twenty-worker
#    volumes:
#      - ./ai-providers.json:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json:ro
#    environment:
#      OPENAI_API_KEY: sk-or-v1-YOUR_KEY

# 4. Force-recreate both containers
docker compose up -d --force-recreate twenty-server twenty-worker
```

## Enable models in DB

After containers are up:

```sql
UPDATE core."workspace" SET
  "enabledAiModelIds" = ARRAY[
    'frontier/anthropic/claude-sonnet-4.5',
    'frontier/openai/gpt-4o',
    'recommended/openai/gpt-4o-mini',
    'recommended/google/gemini-2.5-flash'
    -- add others as needed
  ],
  "smartModel" = 'frontier/anthropic/claude-sonnet-4.5',
  "fastModel" = 'recommended/openai/gpt-4o-mini',
  "useRecommendedModels" = false
WHERE id = 'YOUR_WORKSPACE_ID';
```

Also insert the API key so the LLM config hash changes and the registry rebuilds:

```sql
INSERT INTO core."keyValuePair" (id, "workspaceId", key, value, type, "createdAt", "updatedAt")
VALUES (gen_random_uuid(), NULL, 'OPENAI_API_KEY', '"sk-or-v1-YOUR_KEY"', 'CONFIG_VARIABLE', NOW(), NOW())
ON CONFLICT DO NOTHING;
```

## OpenRouter settings

Go to [openrouter.ai/settings/privacy](https://openrouter.ai/settings/privacy) — disable all **Zero Data Retention** toggles. ZDR blocks many endpoints and causes "No endpoints available" errors.

## Re-applying after a Twenty update

```bash
docker cp twenty-server:/app/.../ai-providers.json ./ai-providers-orig.json
python3 patch.py --input ai-providers-orig.json --output ai-providers.json --key sk-or-v1-YOUR_KEY
docker compose up -d --force-recreate twenty-server twenty-worker
```

## Tested on
- Twenty v2.37.4
- OpenRouter with Claude Sonnet 4.5 (smart) + GPT-4o Mini (fast)
