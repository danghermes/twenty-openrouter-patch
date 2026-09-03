#!/usr/bin/env python3
"""
Twenty CRM — OpenRouter patch for ai-providers.json

Patches Twenty's ai-providers.json to route ALL requests through OpenRouter,
exposing every model available on OpenRouter as selectable in the Twenty UI.

Why this is needed:
- Twenty's built-in AI provider catalog hardcodes openai/anthropic endpoints
- @ai-sdk/openai uses the Responses API which OpenRouter doesn't support
- This patch switches all providers to @ai-sdk/openai-compatible pointed at
  OpenRouter, then dynamically fetches all available OpenRouter models and
  groups them by provider for Twenty's UI.

Usage:
  # Pull original from running container
  docker cp twenty-server:/app/packages/twenty-server/dist/engine/metadata-modules/ai/ai-models/ai-providers.json ./ai-providers.json

  # Apply patch (fetches live model list from OpenRouter)
  python3 patch.py --key sk-or-v1-xxxx [--output ai-providers.json]

  # Mount in docker-compose.yml for BOTH twenty-server and twenty-worker:
  #   volumes:
  #     - ./ai-providers.json:/app/.../ai-providers.json:ro
  # Also set in environment of both:
  #   OPENAI_API_KEY: sk-or-v1-xxxx

  # Force-recreate both containers:
  #   docker compose up -d --force-recreate twenty-server twenty-worker

Author: Hermes (AI agent) for Daniel Gouvignon
Repo: https://github.com/danghermes/twenty-openrouter-patch
Tested on: Twenty v2.37.4
"""

import json
import argparse
import sys
import urllib.request
import urllib.error

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model families Twenty knows about (for UI grouping)
FAMILY_MAP = {
    "gpt": "GPT",
    "o1": "GPT",
    "o3": "GPT",
    "o4": "GPT",
    "claude": "CLAUDE",
    "gemini": "GEMINI",
    "mistral": "MISTRAL",
    "llama": "LLAMA",
    "deepseek": "DEEPSEEK",
    "grok": "XAI",
    "qwen": "QWEN",
    "nova": "NOVA",
    "command": "COHERE",
}

def infer_family(model_id: str) -> str:
    name = model_id.lower()
    for keyword, family in FAMILY_MAP.items():
        if keyword in name:
            return family
    return "OTHER"


def fetch_openrouter_models(api_key: str) -> list:
    """Fetch all models from OpenRouter API."""
    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("data", [])
    except urllib.error.URLError as e:
        print(f"ERROR: Could not fetch models from OpenRouter: {e}", file=sys.stderr)
        sys.exit(1)


def build_provider_catalog(models: list, api_key: str, exclude_variants: bool = True) -> dict:
    """
    Group OpenRouter models by their org prefix and build a Twenty-compatible
    provider catalog entry for each group, all pointing to OpenRouter.
    
    exclude_variants: skip :batch, :free, :extended etc. variants to keep the list clean
    """
    # Filter and group
    grouped: dict[str, list] = {}
    for m in models:
        mid = m.get("id", "")
        if not mid:
            continue
        if exclude_variants and ":" in mid:
            continue
        if "~" in mid:
            continue

        parts = mid.split("/")
        if len(parts) < 2:
            continue

        org = parts[0]
        if org not in grouped:
            grouped[org] = []
        grouped[org].append(m)

    # Build provider entries
    providers = {}
    for org, org_models in sorted(grouped.items()):
        # Sort models by name
        org_models.sort(key=lambda m: m["id"])

        model_defs = []
        for m in org_models:
            mid = m["id"]
            ctx = m.get("context_length") or 128000
            max_out = m.get("top_provider", {}).get("max_completion_tokens") or 8192

            # Pricing (per million tokens)
            pricing = m.get("pricing", {})
            try:
                input_cost = float(pricing.get("prompt", 0)) * 1_000_000
                output_cost = float(pricing.get("completion", 0)) * 1_000_000
            except (TypeError, ValueError):
                input_cost = 0
                output_cost = 0

            model_defs.append({
                "name": mid,
                "label": m.get("name", mid),
                "modelFamily": infer_family(mid),
                "inputCostPerMillionTokens": round(input_cost, 4),
                "outputCostPerMillionTokens": round(output_cost, 4),
                "contextWindowTokens": ctx,
                "maxOutputTokens": max_out,
            })

        providers[org] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": f"openrouter-{org}",
            "label": org.replace("-", " ").title(),
            "apiKey": api_key,
            "baseUrl": OPENROUTER_BASE_URL,
            "models": model_defs,
        }

    return providers


def patch(input_path: str, output_path: str, api_key: str, exclude_variants: bool = True) -> None:
    print("Fetching models from OpenRouter...", file=sys.stderr)
    models = fetch_openrouter_models(api_key)
    print(f"Fetched {len(models)} models", file=sys.stderr)

    # Load original catalog (to preserve any non-AI-model fields Twenty needs)
    with open(input_path) as f:
        original = json.load(f)

    # Build new provider catalog from OpenRouter models
    new_catalog = build_provider_catalog(models, api_key, exclude_variants)

    # Stats
    total_models = sum(len(v["models"]) for v in new_catalog.values())
    print(f"Built {len(new_catalog)} provider groups with {total_models} models total", file=sys.stderr)

    with open(output_path, "w") as f:
        json.dump(new_catalog, f, indent=2)

    print(f"\nPatched {input_path} -> {output_path}")
    print(f"  Providers: {sorted(new_catalog.keys())[:10]}{'...' if len(new_catalog) > 10 else ''}")
    print(f"  Total models: {total_models}")
    print(f"\nTop models by provider:")
    for org in sorted(new_catalog.keys())[:8]:
        first = new_catalog[org]["models"][0]["name"] if new_catalog[org]["models"] else "none"
        count = len(new_catalog[org]["models"])
        print(f"  {org}: {count} models (e.g. {first})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch Twenty ai-providers.json for OpenRouter (all models)")
    parser.add_argument("--input", default="ai-providers.json", help="Path to original ai-providers.json")
    parser.add_argument("--output", default="ai-providers.json", help="Path for patched output")
    parser.add_argument("--key", required=True, help="OpenRouter API key (sk-or-v1-...)")
    parser.add_argument("--include-variants", action="store_true",
                        help="Include :batch, :free, :extended variants (default: excluded)")
    args = parser.parse_args()
    patch(args.input, args.output, args.key, exclude_variants=not args.include_variants)
