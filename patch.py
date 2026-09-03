#!/usr/bin/env python3
"""
Twenty CRM — OpenRouter patch for ai-providers.json

Patches Twenty's ai-providers.json with a curated two-tier model list:
  - FRONTIER: Best-in-class models for complex agentic tasks, due diligence,
    reasoning, and document analysis. Worth the cost for high-value workflows.
  - RECOMMENDED: Strong general-purpose models at sensible price/performance.
    Good defaults for everyday CRM tasks and automation.

Both groups use @ai-sdk/openai-compatible routed through OpenRouter.

Why this is needed:
- Twenty's built-in @ai-sdk/openai uses the Responses API — OpenRouter doesn't support it
- Custom baseUrl requires @ai-sdk/openai-compatible
- Twenty's provider registry needs models pre-registered with composite IDs

Usage:
  docker cp twenty-server:/app/.../ai-providers.json ./ai-providers.json
  python3 patch.py --key sk-or-v1-xxxx [--output ai-providers.json]

  Mount in docker-compose.yml for BOTH twenty-server and twenty-worker:
    volumes:
      - ./ai-providers.json:/app/.../ai-providers.json:ro
  Set in environment of both:
    OPENAI_API_KEY: sk-or-v1-xxxx

  docker compose up -d --force-recreate twenty-server twenty-worker

Author: Hermes (AI agent) for Daniel Gouvignon
Repo: https://github.com/danghermes/twenty-openrouter-patch
Tested on: Twenty v2.37.4
"""

import json
import argparse
import sys

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Model catalog — grouped by provider for the UI's Provider column.
# Each provider entry gets a label Twenty displays in the Provider column.
# Tier (★ Frontier / Recommended) is shown as a prefix in the model label.
# Price is shown in the hover card from inputCost/outputCost fields.
# ---------------------------------------------------------------------------

# provider_key -> { label, models: [...] }
# Model name must be the full OpenRouter ID (org/model-name)
# buildCompositeModelId(provider_key, model_name):
#   if model_name starts with provider_key: returns model_name unchanged
#   else: returns provider_key/model_name
# So we set provider_key = first segment of model_name to avoid double-prefix.

PROVIDERS: dict = {
    "anthropic": {
        "label": "Anthropic",
        "models": [
            {
                "name": "anthropic/claude-sonnet-4.5",
                "label": "★ Claude Sonnet 4.5",
                "modelFamily": "CLAUDE",
                "inputCostPerMillionTokens": 3.0,
                "outputCostPerMillionTokens": 15.0,
                "contextWindowTokens": 200000,
                "maxOutputTokens": 8192,
            },
            {
                "name": "anthropic/claude-opus-4.5",
                "label": "★ Claude Opus 4.5",
                "modelFamily": "CLAUDE",
                "inputCostPerMillionTokens": 5.0,
                "outputCostPerMillionTokens": 25.0,
                "contextWindowTokens": 200000,
                "maxOutputTokens": 8192,
            },
            {
                "name": "anthropic/claude-haiku-4.5",
                "label": "Claude Haiku 4.5",
                "modelFamily": "CLAUDE",
                "inputCostPerMillionTokens": 0.8,
                "outputCostPerMillionTokens": 4.0,
                "contextWindowTokens": 200000,
                "maxOutputTokens": 8192,
            },
        ],
    },
    "openai": {
        "label": "OpenAI",
        "models": [
            {
                "name": "openai/gpt-4o",
                "label": "★ GPT-4o",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 2.5,
                "outputCostPerMillionTokens": 10.0,
                "contextWindowTokens": 128000,
                "maxOutputTokens": 16384,
            },
            {
                "name": "openai/gpt-4.1",
                "label": "★ GPT-4.1",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 2.0,
                "outputCostPerMillionTokens": 8.0,
                "contextWindowTokens": 1047552,
                "maxOutputTokens": 32768,
            },
            {
                "name": "openai/o3",
                "label": "★ o3 · reasoning",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 2.0,
                "outputCostPerMillionTokens": 8.0,
                "contextWindowTokens": 200000,
                "maxOutputTokens": 100000,
                "supportsReasoning": True,
            },
            {
                "name": "openai/o4-mini",
                "label": "★ o4-mini · reasoning",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 1.1,
                "outputCostPerMillionTokens": 4.4,
                "contextWindowTokens": 200000,
                "maxOutputTokens": 100000,
                "supportsReasoning": True,
            },
            {
                "name": "openai/gpt-4o-mini",
                "label": "GPT-4o Mini",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 0.15,
                "outputCostPerMillionTokens": 0.6,
                "contextWindowTokens": 128000,
                "maxOutputTokens": 16384,
            },
            {
                "name": "openai/gpt-4.1-mini",
                "label": "GPT-4.1 Mini",
                "modelFamily": "GPT",
                "inputCostPerMillionTokens": 0.4,
                "outputCostPerMillionTokens": 1.6,
                "contextWindowTokens": 1047552,
                "maxOutputTokens": 32768,
            },
        ],
    },
    "google": {
        "label": "Google",
        "models": [
            {
                "name": "google/gemini-2.5-pro",
                "label": "★ Gemini 2.5 Pro",
                "modelFamily": "GEMINI",
                "inputCostPerMillionTokens": 1.25,
                "outputCostPerMillionTokens": 10.0,
                "contextWindowTokens": 1048576,
                "maxOutputTokens": 65536,
            },
            {
                "name": "google/gemini-2.5-flash",
                "label": "Gemini 2.5 Flash",
                "modelFamily": "GEMINI",
                "inputCostPerMillionTokens": 0.3,
                "outputCostPerMillionTokens": 2.5,
                "contextWindowTokens": 1048576,
                "maxOutputTokens": 65536,
            },
        ],
    },
    "deepseek": {
        "label": "DeepSeek",
        "models": [
            {
                "name": "deepseek/deepseek-r1-0528",
                "label": "★ DeepSeek R1 · reasoning",
                "modelFamily": "DEEPSEEK",
                "inputCostPerMillionTokens": 0.5,
                "outputCostPerMillionTokens": 2.19,
                "contextWindowTokens": 163840,
                "maxOutputTokens": 32768,
                "supportsReasoning": True,
            },
            {
                "name": "deepseek/deepseek-chat-v3.1",
                "label": "DeepSeek V3.1",
                "modelFamily": "DEEPSEEK",
                "inputCostPerMillionTokens": 0.25,
                "outputCostPerMillionTokens": 1.1,
                "contextWindowTokens": 163840,
                "maxOutputTokens": 16384,
            },
        ],
    },
    "xai": {
        "label": "xAI",
        "models": [
            {
                "name": "xai/grok-3",
                "label": "★ Grok 3",
                "modelFamily": "XAI",
                "inputCostPerMillionTokens": 3.0,
                "outputCostPerMillionTokens": 15.0,
                "contextWindowTokens": 131072,
                "maxOutputTokens": 16384,
            },
        ],
    },
    "moonshotai": {
        "label": "Moonshot AI (Kimi)",
        "models": [
            {
                "name": "moonshotai/kimi-k3",
                "label": "★ Kimi K3",
                "modelFamily": "OTHER",
                "inputCostPerMillionTokens": 3.0,
                "outputCostPerMillionTokens": 15.0,
                "contextWindowTokens": 1048576,
                "maxOutputTokens": 32768,
            },
            {
                "name": "moonshotai/kimi-k2",
                "label": "Kimi K2",
                "modelFamily": "OTHER",
                "inputCostPerMillionTokens": 0.57,
                "outputCostPerMillionTokens": 2.3,
                "contextWindowTokens": 131072,
                "maxOutputTokens": 16384,
            },
        ],
    },
    "meta-llama": {
        "label": "Meta",
        "models": [
            {
                "name": "meta-llama/llama-3.3-70b-instruct",
                "label": "Llama 3.3 70B",
                "modelFamily": "LLAMA",
                "inputCostPerMillionTokens": 0.1,
                "outputCostPerMillionTokens": 0.4,
                "contextWindowTokens": 131072,
                "maxOutputTokens": 16384,
            },
            {
                "name": "meta-llama/llama-4-maverick",
                "label": "Llama 4 Maverick",
                "modelFamily": "LLAMA",
                "inputCostPerMillionTokens": 0.2,
                "outputCostPerMillionTokens": 0.8,
                "contextWindowTokens": 1048576,
                "maxOutputTokens": 16384,
            },
        ],
    },
    "mistralai": {
        "label": "Mistral AI",
        "models": [
            {
                "name": "mistralai/mistral-medium-3.1",
                "label": "Mistral Medium 3.1",
                "modelFamily": "MISTRAL",
                "inputCostPerMillionTokens": 0.4,
                "outputCostPerMillionTokens": 2.0,
                "contextWindowTokens": 131072,
                "maxOutputTokens": 16384,
            },
        ],
    },
}


def build_catalog(api_key: str) -> dict:
    """Build one provider entry per org, all pointing to OpenRouter."""
    base = {
        "npm": "@ai-sdk/openai-compatible",
        "apiKey": api_key,
        "baseUrl": OPENROUTER_BASE_URL,
    }

    catalog = {}
    for provider_key, config in PROVIDERS.items():
        catalog[provider_key] = {
            **base,
            "name": f"openrouter-{provider_key}",
            "label": config["label"],
            "models": config["models"],
        }
    return catalog


def patch(input_path: str, output_path: str, api_key: str) -> None:
    catalog = build_catalog(api_key)

    with open(output_path, "w") as f:
        json.dump(catalog, f, indent=2)

    total = sum(len(v["models"]) for v in catalog.values())
    frontier = sum(1 for p in catalog.values() for m in p["models"] if m["label"].startswith("★"))
    print(f"Patched -> {output_path}  ({total} models across {len(catalog)} providers, {frontier} frontier)")
    print()
    for pk, pv in catalog.items():
        for m in pv["models"]:
            tier = "★" if m["label"].startswith("★") else " "
            print(f"  {tier} {pv['label']:25s}  {m['name']:50s}  ${m['inputCostPerMillionTokens']:.3f}/Mtok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Twenty ai-providers.json — curated OpenRouter model list")
    parser.add_argument("--input", default="ai-providers.json", help="Path to original ai-providers.json (not modified)")
    parser.add_argument("--output", default="ai-providers.json", help="Output path")
    parser.add_argument("--key", required=True, help="OpenRouter API key (sk-or-v1-...)")
    args = parser.parse_args()
    patch(args.input, args.output, args.key)
