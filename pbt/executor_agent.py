"""Agent 3, Test Executor: runs the tests in a scratch folder under branch coverage and
turns pytest/Hypothesis/coverage output into a verdict.

Deliberately rule-based: verdicts come from executing code, never from an LLM's opinion,
so the same files always produce the same verdict.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONFTEST = '''import json
from hypothesis import HealthCheck, settings

settings.register_profile("pipeline", max_examples={max_examples}, deadline=None,
                          database=None, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("pipeline")
_results = []

def pytest_collectreport(report):
    if report.failed:
        _results.append({{"test": "<collection>", "outcome": "error",
                          "detail": report.longreprtext[-4000:]}})

def pytest_runtest_logreport(report):
    if report.when == "call" or report.failed:
        _results.append({{"test": report.nodeid.split("::")[-1], "outcome": report.outcome,
                          "detail": report.longreprtext[-4000:] if report.failed else ""}})

def pytest_sessionfinish(session, exitstatus):
    with open("results.json", "w") as f:
        json.dump({{"exitstatus": int(exitstatus), "tests": _results}}, f, indent=2)
'''

# Hypothesis prints "Falsifying example:" in older releases and "Failing test case:" in newer ones.
FAILING = re.compile(r"(?:Falsifying|Failing)(?: explicit)? (?:example|test case):")
LOCATION = re.compile(r"^([\w./\\-]+\.py):(\d+): (\w[\w.]*)", re.M)


@dataclass
class PropertyResult:
    test: str
    status: str                       # HOLDS | FALSIFIED | TEST_ERROR
    counterexample: str | None = None
    error: str | None = None          # e.g. "IndexError at solution.py:2"
    detail: str = ""


@dataclass
class RunResult:
    status: str                       # OK | COLLECTION_ERROR | TIMEOUT
    properties: list[PropertyResult] = field(default_factory=list)
    branch_pct: float | None = None
    covered_branches: int = 0
    num_branches: int = 0
    missing_branches: list[list[int]] = field(default_factory=list)
    log_tail: str = ""

    @property
    def clean(self) -> bool:
        return self.status == "OK" and all(p.status != "TEST_ERROR" for p in self.properties)

    @property
    def falsified(self) -> list[PropertyResult]:
        return [p for p in self.properties if p.status == "FALSIFIED"]

    def error_text(self) -> str:
        bad = [f"{p.test}: {p.detail}" for p in self.properties if p.status == "TEST_ERROR"]
        return "\n\n".join(bad) or self.log_tail

    def summary(self) -> dict:
        return {"status": self.status, "branch_pct": self.branch_pct,
                "branches": f"{self.covered_branches}/{self.num_branches}",
                "missing_branches": self.missing_branches,
                "properties": [{"test": p.test, "status": p.status, "counterexample": p.counterexample,
                                "error": p.error} for p in self.properties]}


def extract_counterexample(detail: str) -> str | None:
    m = FAILING.search(detail)
    if not m:
        return None
    parts = []
    for line in detail[m.end():].splitlines():
        line = line.lstrip("E").strip().split("  #")[0].strip()
        if not line:
            continue
        parts.append(line)
        if line.endswith(")") and line.count("(") <= line.count(")"):
            break
    return " ".join(parts).replace("( ", "(").replace(", )", ")")


def classify(t: dict) -> PropertyResult:
    if t["outcome"] == "passed":
        return PropertyResult(t["test"], "HOLDS")
    detail = t["detail"]
    where = LOCATION.findall(detail)
    error = f"{where[-1][2]} at {Path(where[-1][0]).name}:{where[-1][1]}" if where else None
    status = "FALSIFIED" if FAILING.search(detail) else "TEST_ERROR"
    return PropertyResult(t["test"], status, extract_counterexample(detail), error, detail[-1500:])


class ExecutorAgent:
    name = "executor"

    def __init__(self, max_examples: int, seed: int, timeout: int):
        self.max_examples, self.seed, self.timeout = max_examples, seed, timeout

    def run(self, solution: str, tests: str, workdir: Path, coverage: bool = True) -> RunResult:
        workdir.mkdir(parents=True, exist_ok=True)
        for stale in ("results.json", ".coverage", "cov.json"):
            (workdir / stale).unlink(missing_ok=True)
        (workdir / "solution.py").write_text(solution)
        (workdir / "test_solution.py").write_text(tests)
        (workdir / "conftest.py").write_text(CONFTEST.format(max_examples=self.max_examples))
        pytest = ["-m", "pytest", "-q", "-p", "no:cacheprovider",
                  f"--hypothesis-seed={self.seed}", "test_solution.py"]
        cmd = [sys.executable, "-B", *(["-m", "coverage", "run", "--branch", "--include=solution.py"]
                                 if coverage else []), *pytest]
        try:
            p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return RunResult("TIMEOUT", log_tail=f"no result after {self.timeout}s (infinite loop?)")
        (workdir / "pytest.log").write_text(p.stdout + p.stderr)
        tail = (p.stdout + p.stderr)[-3000:]
        results = workdir / "results.json"
        if not results.exists():
            return RunResult("COLLECTION_ERROR", log_tail=tail)
        raw = json.loads(results.read_text())
        if raw["exitstatus"] not in (0, 1) or any(t["test"] == "<collection>" for t in raw["tests"]):
            return RunResult("COLLECTION_ERROR", log_tail=tail)
        result = RunResult("OK", [classify(t) for t in raw["tests"]], log_tail=tail)
        if coverage:
            self._read_coverage(result, workdir)
        return result

    def _read_coverage(self, result: RunResult, workdir: Path) -> None:
        subprocess.run([sys.executable, "-m", "coverage", "json", "-q", "-o", "cov.json"],
                       cwd=workdir, capture_output=True, text=True, timeout=60)
        cov = workdir / "cov.json"
        if not cov.exists():
            return
        files = json.loads(cov.read_text())["files"]
        entry = next((v for k, v in files.items() if Path(k).name == "solution.py"), None)
        if entry is None:
            return
        s = entry["summary"]
        result.num_branches = s.get("num_branches", 0)
        result.covered_branches = s.get("covered_branches", 0)
        result.branch_pct = (100.0 if result.num_branches == 0 else
                             round(100 * result.covered_branches / result.num_branches, 1))
        result.missing_branches = entry.get("missing_branches", [])

    def humaneval_check(self, solution: str, check_src: str, entry_point: str, workdir: Path) -> bool:
        """Evaluation only: does the generated code pass HumanEval's own hidden tests?"""
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "humaneval_check.py").write_text(f"{solution}\n\n{check_src}\n\ncheck({entry_point})\n")
        try:
            p = subprocess.run([sys.executable, "-B", "humaneval_check.py"], cwd=workdir,
                               capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            return False
        return p.returncode == 0
