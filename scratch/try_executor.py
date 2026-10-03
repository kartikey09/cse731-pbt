"""Day 2 check of the executor with no model involved: the same hand-written tests
against HumanEval's reference solution and against a planted bug.

Usage: python scratch/try_executor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.data import load_problems            # noqa: E402
from pbt.executor_agent import ExecutorAgent  # noqa: E402

problem = load_problems("data/HumanEval.jsonl.gz", "properties.yaml", ["HumanEval/26"])[0]
tests = Path("scratch/props_remove_duplicates.py").read_text()
planted_bug = "def remove_duplicates(numbers):\n    return list(dict.fromkeys(numbers))  # dedupes instead\n"
executor = ExecutorAgent(max_examples=200, seed=0, timeout=60)

for name, code in [("reference", problem.reference), ("planted_bug", planted_bug)]:
    result = executor.run(code, tests, Path("scratch/executor") / name)
    print(f"\n{name}: {result.status}, branch coverage {result.branch_pct}%")
    for p in result.properties:
        print(f"  {p.test:<46} {p.status:<10} {p.counterexample or ''}")
