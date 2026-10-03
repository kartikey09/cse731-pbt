"""Day 2 task 6: provoke every verdict on purpose, with no LLM involved.

PASS and TEST_BUG already showed up in a real run (runs/day2_full/). This drives
pbt.pipeline.solve() directly with fixed solution/test strings to force the three
verdicts that didn't occur naturally: CODE_BUG, WEAK_PASS, ERROR.

Usage: python scratch/demo_verdicts.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pbt.data import load_problems       # noqa: E402
from pbt.executor_agent import ExecutorAgent  # noqa: E402
from pbt.pipeline import solve           # noqa: E402

problem = load_problems("data/HumanEval.jsonl.gz", "properties.yaml", ["HumanEval/26"])[0]
correct_tests = Path("scratch/props_remove_duplicates.py").read_text()
executor = ExecutorAgent(max_examples=200, seed=0, timeout=60)
cfg = {"coverage_threshold": 90, "max_rounds": 3}
out_dir = Path("scratch/verdict_demo")
shutil.rmtree(out_dir, ignore_errors=True)


class FixedCode:
    """Stands in for CodeGenAgent: always returns the same solution.py."""
    def __init__(self, src: str):
        self.src = src

    def run(self, problem):
        return self.src


class FixedTests:
    """Stands in for TestGenAgent: same reply to generate/repair/widen."""
    def __init__(self, src: str):
        self.src = src

    def generate(self, problem):
        return self.src

    def repair(self, problem, tests, error):
        return self.src

    def widen(self, problem, tests, solution, branch_pct, threshold, missing, drifted=None):
        return self.src


def run_case(name: str, code: str, tests: str) -> None:
    print(f"\n=== {name} ===")
    record = solve(problem, FixedCode(code), FixedTests(tests), executor, cfg, out_dir / name)
    print(f"{name}: verdict={record['verdict']}  stop={record['stop_reason']}")


# 1. CODE_BUG: a dedupe bug (plan's hero example) against the correct hand-written tests.
#    "remove_duplicates" should drop every element that repeats; this merely de-duplicates,
#    so P1 ("every result element occurs exactly once in the input") breaks on this code and
#    holds on HumanEval's reference -> CODE_BUG.
planted_bug = "def remove_duplicates(numbers):\n    return list(dict.fromkeys(numbers))  # dedupes instead\n"
run_case("code_bug", planted_bug, correct_tests)

# 2. WEAK_PASS: a branchy (but correct) solution, tested only on the empty list.
#    The reference's one-line comprehension has no line-level branch for coverage.py to
#    miss, so this uses an equivalent two-loop version with real if/else branches instead.
#    Properties hold vacuously on "[]", coverage stays low, and since FixedTests.widen()
#    returns the same source every round, the orchestrator sees no coverage gain and stops
#    below the 90% threshold.
branchy_solution = '''def remove_duplicates(numbers):
    seen, dupes = set(), set()
    for n in numbers:
        if n in seen:
            dupes.add(n)
        else:
            seen.add(n)
    result = []
    for n in numbers:
        if n not in dupes:
            result.append(n)
    return result
'''
weak_tests = '''from hypothesis import given, strategies as st
from solution import remove_duplicates

only_empty = st.just([])

@given(only_empty)
def test_p1_result_elements_occur_once_in_input(xs):
    assert remove_duplicates(list(xs)) == []

@given(only_empty)
def test_p2_unique_inputs_are_kept(xs):
    assert remove_duplicates(list(xs)) == []

@given(only_empty)
def test_p3_order_preserved(xs):
    assert remove_duplicates(list(xs)) == []
'''
run_case("weak_pass", branchy_solution, weak_tests)

# 3. ERROR: the test module never parses, in every round including the "repaired" one.
broken_tests = "def test_p1_broken(:\n    this is not python\n"
run_case("error", problem.reference, broken_tests)
