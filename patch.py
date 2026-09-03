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
# FRONTIER — best-in-class for agentic CRM work
# Criteria: top reasoning, tool use, long context, vision, proven reliability
# ---------------------------------------------------------------------------
FRONTIER_MODELS = [
    # Anthropic
    {
        "name": "anthropic/claude-sonnet-4.5",
        "label": "Claude Sonnet 4.5 ★",
        "modelFamily": "CLAUDE",
        "inputCostPerMillionTokens": 3.0,
        "outputCostPerMillionTokens": 15.0,
        "contextWindowTokens": 200000,
        "maxOutputTokens": 8192,
        "modalities": ["text", "image"],
    },
    {
        "name": "anthropic/claude-opus-4.5",
        "label": "Claude Opus 4.5",
        "modelFamily": "CLAUDE",
        "inputCostPerMillionTokens": 5.0,
        "outputCostPerMillionTokens": 25.0,
        "contextWindowTokens": 200000,
        "maxOutputTokens": 8192,
        "modalities": ["text", "image"],
    },
    # OpenAI
    {
        "name": "openai/gpt-4o",
        "label": "GPT-4o ★",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 2.5,
        "outputCostPerMillionTokens": 10.0,
        "contextWindowTokens": 128000,
        "maxOutputTokens": 16384,
        "modalities": ["text", "image"],
    },
    {
        "name": "openai/gpt-4.1",
        "label": "GPT-4.1",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 2.0,
        "outputCostPerMillionTokens": 8.0,
        "contextWindowTokens": 1047552,
        "maxOutputTokens": 32768,
        "modalities": ["text", "image"],
    },
    {
        "name": "openai/o3",
        "label": "o3 (reasoning)",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 2.0,
        "outputCostPerMillionTokens": 8.0,
        "contextWindowTokens": 200000,
        "maxOutputTokens": 100000,
        "supportsReasoning": True,
        "modalities": ["text", "image"],
    },
    {
        "name": "openai/o4-mini",
        "label": "o4-mini (reasoning)",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 1.1,
        "outputCostPerMillionTokens": 4.4,
        "contextWindowTokens": 200000,
        "maxOutputTokens": 100000,
        "supportsReasoning": True,
        "modalities": ["text", "image"],
    },
    # Google
    {
        "name": "google/gemini-2.5-pro",
        "label": "Gemini 2.5 Pro",
        "modelFamily": "GEMINI",
        "inputCostPerMillionTokens": 1.25,
        "outputCostPerMillionTokens": 10.0,
        "contextWindowTokens": 1048576,
        "maxOutputTokens": 65536,
        "modalities": ["text", "image"],
    },
    # DeepSeek
    {
        "name": "deepseek/deepseek-r1-0528",
        "label": "DeepSeek R1 (reasoning)",
        "modelFamily": "DEEPSEEK",
        "inputCostPerMillionTokens": 0.5,
        "outputCostPerMillionTokens": 2.19,
        "contextWindowTokens": 163840,
        "maxOutputTokens": 32768,
        "supportsReasoning": True,
        "modalities": ["text"],
    },
    # xAI
    {
        "name": "xai/grok-3",
        "label": "Grok 3",
        "modelFamily": "XAI",
        "inputCostPerMillionTokens": 3.0,
        "outputCostPerMillionTokens": 15.0,
        "contextWindowTokens": 131072,
        "maxOutputTokens": 16384,
        "modalities": ["text"],
    },
]

# ---------------------------------------------------------------------------
# RECOMMENDED — strong everyday models at sensible cost
# Criteria: good reasoning, reliable tool use, cost-effective for CRM tasks
# ---------------------------------------------------------------------------
RECOMMENDED_MODELS = [
    # Anthropic
    {
        "name": "anthropic/claude-haiku-4.5",
        "label": "Claude Haiku 4.5 (fast)",
        "modelFamily": "CLAUDE",
        "inputCostPerMillionTokens": 0.8,
        "outputCostPerMillionTokens": 4.0,
        "contextWindowTokens": 200000,
        "maxOutputTokens": 8192,
        "modalities": ["text", "image"],
    },
    # OpenAI
    {
        "name": "openai/gpt-4o-mini",
        "label": "GPT-4o Mini (fast)",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 0.15,
        "outputCostPerMillionTokens": 0.6,
        "contextWindowTokens": 128000,
        "maxOutputTokens": 16384,
        "modalities": ["text", "image"],
    },
    {
        "name": "openai/gpt-4.1-mini",
        "label": "GPT-4.1 Mini",
        "modelFamily": "GPT",
        "inputCostPerMillionTokens": 0.4,
        "outputCostPerMillionTokens": 1.6,
        "contextWindowTokens": 1047552,
        "maxOutputTokens": 32768,
        "modalities": ["text", "image"],
    },
    # Google
    {
        "name": "google/gemini-2.5-flash",
        "label": "Gemini 2.5 Flash (fast)",
        "modelFamily": "GEMINI",
        "inputCostPerMillionTokens": 0.3,
        "outputCostPerMillionTokens": 2.5,
        "contextWindowTokens": 1048576,
        "maxOutputTokens": 65536,
        "modalities": ["text", "image"],
    },
    # DeepSeek
    {
        "name": "deepseek/deepseek-chat-v3.1",
        "label": "DeepSeek V3.1 (value)",
        "modelFamily": "DEEPSEEK",
        "inputCostPerMillionTokens": 0.25,
        "outputCostPerMillionTokens": 1.1,
        "contextWindowTokens": 163840,
        "maxOutputTokens": 16384,
        "modalities": ["text"],
    },
    # Meta
    {
        "name": "meta-llama/llama-3.3-70b-instruct",
        "label": "Llama 3.3 70B (open)",
        "modelFamily": "LLAMA",
        "inputCostPerMillionTokens": 0.1,
        "outputCostPerMillionTokens": 0.4,
        "contextWindowTokens": 131072,
        "maxOutputTokens": 16384,
        "modalities": ["text"],
    },
    # Mistral
    {
        "name": "mistralai/mistral-medium-3.1",
        "label": "Mistral Medium 3.1",
        "modelFamily": "MISTRAL",
        "inputCostPerMillionTokens": 0.4,
        "outputCostPerMillionTokens": 2.0,
        "contextWindowTokens": 131072,
        "maxOutputTokens": 16384,
        "modalities": ["text", "image"],
    },
]


def build_catalog(api_key: str) -> dict:
    """Build Two provider entries: 'frontier' and 'recommended'."""
    base = {
        "npm": "@ai-sdk/openai-compatible",
        "apiKey": api_key,
        "baseUrl": OPENROUTER_BASE_URL,
    }

    return {
        "frontier": {
            **base,
            "name": "openrouter-frontier",
            "label": "Frontier Models",
            "models": FRONTIER_MODELS,
        },
        "recommended": {
            **base,
            "name": "openrouter-recommended",
            "label": "Recommended Models",
            "models": RECOMMENDED_MODELS,
        },
    }


def patch(input_path: str, output_path: str, api_key: str) -> None:
    catalog = build_catalog(api_key)

    with open(output_path, "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"Patched -> {output_path}")
    print(f"\n  FRONTIER ({len(FRONTIER_MODELS)} models):")
    for m in FRONTIER_MODELS:
        print(f"    {m['name']:55s}  ${m['inputCostPerMillionTokens']:.3f}/Mtok in")
    print(f"\n  RECOMMENDED ({len(RECOMMENDED_MODELS)} models):")
    for m in RECOMMENDED_MODELS:
        print(f"    {m['name']:55s}  ${m['inputCostPerMillionTokens']:.3f}/Mtok in")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Twenty ai-providers.json — curated OpenRouter model list")
    parser.add_argument("--input", default="ai-providers.json", help="Path to original ai-providers.json (not modified)")
    parser.add_argument("--output", default="ai-providers.json", help="Output path")
    parser.add_argument("--key", required=True, help="OpenRouter API key (sk-or-v1-...)")
    args = parser.parse_args()
    patch(args.input, args.output, args.key)
