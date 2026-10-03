"""Minimal chat client: one HTTP POST per call, every call logged, every response cached.

Works with any OpenAI-compatible endpoint: Ollama on the Mac (local, unlimited) or
OpenRouter (free cloud models). No SDK and no framework, so every byte sent is visible.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """The provider's daily cap is used up: retrying today is pointless."""


# OpenRouter: "free-models-per-day"; Groq: "tokens per day (TPD)" / "requests per day (RPD)"
DAILY_CAP = re.compile(r"per[-_ ]?day|\bTPD\b|\bRPD\b", re.I)


def load_dotenv(path: str = ".env") -> None:
    """Read KEY=value lines from .env into the environment (keeps API keys out of code)."""
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


class LLM:
    def __init__(self, provider: dict, log_path: Path, use_cache: bool = True,
                 cache_dir: Path = Path(".cache/llm")):
        self.base_url = provider["base_url"].rstrip("/")
        key_env = provider.get("api_key_env")
        self.api_key = os.environ.get(key_env) if key_env else None
        if key_env and not self.api_key:
            raise LLMError(f"{key_env} is not set. Put it in .env")
        self.model = provider["model"]
        self.extra = provider.get("extra") or {}
        self.min_interval = float(provider.get("min_interval_s", 0))
        self.log_path, self.use_cache, self.cache_dir = log_path, use_cache, cache_dir
        self.real_calls = 0
        self._last = 0.0

    def chat(self, agent: str, system: str, user: str, params: dict) -> str:
        body = {"model": self.model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                **params, **self.extra}
        key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:32]
        cache_file = self.cache_dir / f"{key}.json"
        if self.use_cache and cache_file.exists():
            entry = json.loads(cache_file.read_text())
            self._log(agent, body, entry, cached=True)
            return entry["text"]
        entry = self._post(body)
        self.real_calls += 1
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(entry))
        self._log(agent, body, entry, cached=False)
        return entry["text"]

    def _post(self, body: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for attempt in range(6):
            gap = self.min_interval - (time.time() - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = t0 = time.time()
            try:
                r = requests.post(f"{self.base_url}/chat/completions", json=body,
                                  headers=headers, timeout=300)
            except requests.RequestException as e:
                problem = f"network error: {e}"
            else:
                if r.status_code == 200 and r.json().get("choices"):
                    data = r.json()
                    return {"text": data["choices"][0]["message"].get("content") or "",
                            "served_model": data.get("model", body["model"]),
                            "usage": data.get("usage"),
                            "latency_s": round(time.time() - t0, 2)}
                if r.status_code == 429 and DAILY_CAP.search(r.text):
                    raise QuotaExhausted(f"{self.model}: daily quota used up. Finished calls are cached, "
                                         "so re-run after the reset or switch --provider. "
                                         f"Provider said: {r.text[:160]}")
                if r.status_code not in (200, 429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
                problem = f"HTTP {r.status_code}: {r.text[:160]}"
            wait = min(60, 5 * 2 ** attempt)
            print(f"    llm: {problem} (retry in {wait}s)")
            time.sleep(wait)
        raise LLMError("LLM call failed 6 times; check the provider, model id and daily limit")

    def _log(self, agent: str, body: dict, entry: dict, cached: bool) -> None:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": agent,
                  "model": body["model"], "served_model": entry.get("served_model"),
                  "params": {k: v for k, v in body.items() if k not in ("model", "messages")},
                  "system": body["messages"][0]["content"],
                  "user": body["messages"][1]["content"],
                  "response": entry["text"], "usage": entry.get("usage"),
                  "latency_s": entry.get("latency_s"), "cached": cached}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps(record) + "\n")
