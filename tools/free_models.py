"""List the OpenRouter models that are free right now (the list rotates every few weeks).

Usage: python tools/free_models.py
Prefer reasoning=none or reasoning=optional: config.yaml switches optional reasoning off.
"""
import requests

models = requests.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]
for m in sorted((m for m in models if m["id"].endswith(":free")), key=lambda m: m["id"]):
    if "reasoning" not in (m.get("supported_parameters") or []):
        mode = "none"
    else:
        mode = "MANDATORY" if (m.get("reasoning") or {}).get("mandatory") else "optional"
    print(f'{m["id"]:<58} context={m.get("context_length", "?"):>9}  reasoning={mode}')
