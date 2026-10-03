"""Day 3: does coverage feedback make the property tests stronger?

Runs the first clean test module and the final test module of every problem against
mutants of the HumanEval reference solution, and reports the mutation score of each.
Usage: python tools/evaluate_mutants.py runs/<name>
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.data import load_problems          # noqa: E402
from pbt.executor_agent import ExecutorAgent  # noqa: E402
from tools.mutate import make_mutants      # noqa: E402


def score(executor, problem, tests: str, mutants: list[dict], work: Path) -> dict:
    ref = executor.run(problem.reference, tests, work / "reference", coverage=False)
    if not ref.clean or ref.falsified:
        return {"valid": False, "note": "tests fail on the reference solution"}

    def kills(m: dict) -> tuple[str, bool]:
        r = executor.run(m["source"], tests, work / m["id"], coverage=False)
        return m["id"], r.status == "TIMEOUT" or bool(r.falsified)

    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2)) as pool:
        killed = dict(pool.map(kills, mutants))
    n = sum(killed.values())
    return {"valid": True, "killed": n, "total": len(mutants),
            "score": round(100 * n / len(mutants), 1) if mutants else None,
            "survivors": [m["change"] for m in mutants if not killed[m["id"]]]}


def main(run_dir: Path) -> None:
    cfg = yaml.safe_load((run_dir / "config_used.yaml").read_text())["pipeline"]
    executor = ExecutorAgent(cfg["hypothesis_max_examples"], cfg["hypothesis_seed"], timeout=20)
    problems = {p.task_id: p for p in load_problems(cfg["dataset"], cfg["properties_file"])}
    report = []
    for vfile in sorted(run_dir.glob("*/verdict.json"), key=lambda f: int(f.parent.name.split("_")[-1])):
        v = json.loads(vfile.read_text())
        if not v.get("first_clean_round"):
            continue
        problem, pdir = problems[v["task_id"]], vfile.parent
        mutants = make_mutants(problem.reference)
        first = (pdir / f"round_{v['first_clean_round']}" / "test_solution.py").read_text()
        final = (pdir / f"round_{v['final_clean_round']}" / "test_solution.py").read_text()
        row = {"task_id": v["task_id"], "entry_point": v["entry_point"], "mutants": len(mutants),
               "first": score(executor, problem, first, mutants, pdir / "mutation" / "first")}
        row["final"] = row["first"] if final == first else score(
            executor, problem, final, mutants, pdir / "mutation" / "final")
        report.append(row)
        f, g = row["first"], row["final"]
        print(f"{v['task_id']:<14} mutants={len(mutants):>2}  first={f.get('score', 'invalid')}  "
              f"final={g.get('score', 'invalid')}")
    (run_dir / "mutation.json").write_text(json.dumps(report, indent=2))
    print(f"wrote {run_dir / 'mutation.json'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
