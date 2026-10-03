"""Entry point.  Examples:
    python run.py                                   # all problems, provider from config.yaml
    python run.py --task HumanEval/26 --name demo   # one problem
    python run.py --provider openrouter --name final   # any key under providers:
    python run.py --max-rounds 1 --name no_feedback # ablation: coverage feedback off
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

import yaml

from pbt.codegen_agent import CodeGenAgent
from pbt.data import load_problems
from pbt.executor_agent import ExecutorAgent
from pbt.llm import LLM, QuotaExhausted, load_dotenv
from pbt.pipeline import solve
from pbt.testgen_agent import TestGenAgent


def main() -> None:
    ap = argparse.ArgumentParser(description="Property-based unit test generation pipeline")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--provider", help="a key under providers: in config.yaml")
    ap.add_argument("--task", action="append", help="HumanEval task id (repeatable)")
    ap.add_argument("--max-rounds", type=int, help="1 turns coverage feedback off")
    ap.add_argument("--no-cache", action="store_true", help="always call the LLM")
    ap.add_argument("--name", default=time.strftime("%Y%m%d-%H%M%S"), help="run folder name")
    args = ap.parse_args()

    load_dotenv()
    cfg = yaml.safe_load(Path(args.config).read_text())
    provider_name = args.provider or cfg["provider"]
    if provider_name not in cfg["providers"]:
        ap.error(f"unknown provider {provider_name!r}; config.yaml has {sorted(cfg['providers'])}")
    pipe = cfg["pipeline"]
    if args.max_rounds:
        pipe["max_rounds"] = args.max_rounds

    out_dir = Path("runs") / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config_used.yaml").write_text(yaml.safe_dump({**cfg, "provider": provider_name}))

    llm = LLM(cfg["providers"][provider_name], out_dir / "llm_log.jsonl", use_cache=not args.no_cache)
    code_agent = CodeGenAgent(llm, cfg["agents"]["code_gen"])
    test_agent = TestGenAgent(llm, cfg["agents"]["test_gen"])
    executor = ExecutorAgent(pipe["hypothesis_max_examples"], pipe["hypothesis_seed"],
                             pipe["exec_timeout_s"])

    records = []
    for problem in load_problems(pipe["dataset"], pipe["properties_file"], args.task):
        try:
            records.append(solve(problem, code_agent, test_agent, executor, pipe, out_dir))
        except QuotaExhausted as e:  # later units would fail the same way
            print(f"\nSTOPPED: {e}")
            break
        except Exception as e:  # one bad problem must not kill the whole run
            print(f"   ERROR: {e}")
            records.append({"task_id": problem.task_id, "entry_point": problem.entry_point,
                            "verdict": "ERROR", "error": str(e)})
    (out_dir / "summary.json").write_text(json.dumps(records, indent=2))
    print(f"\nverdicts: {dict(Counter(r['verdict'] for r in records))}")
    print(f"real LLM calls this run: {llm.real_calls} (others came from .cache/llm)")
    print(f"results in {out_dir}/")


if __name__ == "__main__":
    main()
