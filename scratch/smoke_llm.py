"""Day 1: send one tiny prompt through each provider and print the replies.

Usage: python scratch/smoke_llm.py [provider ...]   (default: the provider in config.yaml)
Each call adds a line to runs/smoke/llm_log.jsonl, so you can see exactly what was sent.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.llm import LLM, load_dotenv  # noqa: E402

load_dotenv()
cfg = yaml.safe_load(Path("config.yaml").read_text())
for name in sys.argv[1:] or [cfg["provider"]]:
    llm = LLM(cfg["providers"][name], Path("runs/smoke/llm_log.jsonl"), use_cache=False)
    reply = llm.chat("smoke", "Answer in one word.", "Say OK.", {"temperature": 0})
    print(f"{name}: {reply.strip()}")
