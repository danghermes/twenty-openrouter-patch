#!/usr/bin/env python3
"""
Twenty CRM — OpenRouter patch for ai-providers.json

This script patches Twenty's ai-providers.json to route OpenAI and Anthropic
requests through OpenRouter instead of directly to the providers.

Why this is needed:
- Twenty's built-in AI provider catalog hardcodes openai/anthropic endpoints
- @ai-sdk/openai uses the Responses API which OpenRouter doesn't support
- This patch switches both providers to @ai-sdk/openai-compatible and sets
  baseUrl to OpenRouter, enabling any model OpenRouter supports.

Usage:
  docker cp twenty-server:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json ./ai-providers.json
  python3 ai-providers.json.patch.py --key sk-or-v1-xxxx
  # Then mount the patched file as a volume in docker-compose.yml

Author: Hermes (AI agent) for Daniel Gouvignon
Repo: https://github.com/danghermes/twenty-openrouter-patch
"""

import json
import argparse
import sys

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

OPENAI_MODELS = [
    {"name": "gpt-4o", "label": "GPT-4o", "modelFamily": "GPT",
     "inputCostPerMillionTokens": 2.5, "outputCostPerMillionTokens": 10,
     "contextWindowTokens": 128000, "maxOutputTokens": 16384},
    {"name": "gpt-4o-mini", "label": "GPT-4o Mini", "modelFamily": "GPT",
     "inputCostPerMillionTokens": 0.15, "outputCostPerMillionTokens": 0.6,
     "contextWindowTokens": 128000, "maxOutputTokens": 16384},
]

ANTHROPIC_MODELS = [
    {"name": "anthropic/claude-sonnet-4.5", "label": "Claude Sonnet 4.5", "modelFamily": "CLAUDE",
     "inputCostPerMillionTokens": 3, "outputCostPerMillionTokens": 15,
     "contextWindowTokens": 200000, "maxOutputTokens": 8192},
    {"name": "anthropic/claude-haiku-4.5", "label": "Claude Haiku 4.5", "modelFamily": "CLAUDE",
     "inputCostPerMillionTokens": 0.8, "outputCostPerMillionTokens": 4,
     "contextWindowTokens": 200000, "maxOutputTokens": 8192},
]


def patch(input_path: str, output_path: str, api_key: str) -> None:
    with open(input_path) as f:
        catalog = json.load(f)

    # Patch openai provider:
    # - switch to @ai-sdk/openai-compatible (avoids Responses API, uses plain chat completions)
    # - set baseUrl to OpenRouter
    # - hardcode api key (template resolution unreliable for non-registered vars)
    catalog["openai"]["npm"] = "@ai-sdk/openai-compatible"
    catalog["openai"]["name"] = "openrouter"
    catalog["openai"]["baseUrl"] = OPENROUTER_BASE_URL
    catalog["openai"]["apiKey"] = api_key
    catalog["openai"]["models"] = OPENAI_MODELS

    # Patch anthropic provider:
    # - @ai-sdk/anthropic does support baseUrl override via createAnthropic({ baseURL })
    # - model names must include org prefix for OpenRouter (anthropic/claude-*)
    # - buildCompositeModelId('anthropic', 'anthropic/claude-*') correctly returns 'anthropic/claude-*'
    catalog["anthropic"]["baseUrl"] = OPENROUTER_BASE_URL
    catalog["anthropic"]["apiKey"] = api_key
    catalog["anthropic"]["models"] = ANTHROPIC_MODELS

    with open(output_path, "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"Patched {input_path} -> {output_path}")
    print(f"  openai: npm={catalog['openai']['npm']}, baseUrl={catalog['openai']['baseUrl']}")
    print(f"  anthropic: baseUrl={catalog['anthropic']['baseUrl']}")
    print(f"  openai models: {[m['name'] for m in catalog['openai']['models']]}")
    print(f"  anthropic models: {[m['name'] for m in catalog['anthropic']['models']]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Twenty ai-providers.json for OpenRouter")
    parser.add_argument("--input", default="ai-providers.json", help="Path to original ai-providers.json")
    parser.add_argument("--output", default="ai-providers.json", help="Path for patched output")
    parser.add_argument("--key", required=True, help="OpenRouter API key (sk-or-v1-...)")
    args = parser.parse_args()
    patch(args.input, args.output, args.key)
