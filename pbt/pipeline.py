"""Orchestrator: plain Python control flow, no agent framework.

code_gen -> test_gen -> executor, then up to max_rounds-1 extra rounds:
  tests broken             -> test_gen.repair(error)                    -> run again
  property falsified       -> stop; triage the failure against HumanEval's reference
  coverage below threshold -> test_gen.widen(uncovered branches)        -> run again
                              (stop early if a round brings no coverage gain)
"""
from __future__ import annotations

import json
from pathlib import Path

from .testgen_agent import assertion_fingerprint


def solve(problem, code_agent, test_agent, executor, cfg: dict, out_dir: Path) -> dict:
    pdir = out_dir / problem.slug
    pdir.mkdir(parents=True, exist_ok=True)
    threshold, max_rounds = cfg["coverage_threshold"], cfg["max_rounds"]
    print(f"\n== {problem.task_id} {problem.entry_point}")

    solution = code_agent.run(problem)
    (pdir / "solution.py").write_text(solution)
    tests = test_agent.generate(problem)

    rounds, frozen, drift, stop = [], None, False, "max rounds"
    best = None                                    # (round, result, tests) of the last clean run
    for rnd in range(1, max_rounds + 1):
        res = executor.run(solution, tests, pdir / f"round_{rnd}")
        rounds.append({"round": rnd, **res.summary()})
        held = sum(p.status == "HOLDS" for p in res.properties)
        print(f"   round {rnd}: {res.status}, {held}/{len(res.properties)} properties hold, "
              f"branch coverage {res.branch_pct}%")

        if not res.clean:                          # broken tests: ask for a repair
            stop = "tests still broken"
            if rnd < max_rounds:
                tests = test_agent.repair(problem, tests, res.error_text())
            continue
        prev, best = best, (rnd, res, tests)
        if frozen is None:
            frozen = assertion_fingerprint(tests)  # the properties are now fixed
        coverage = res.branch_pct or 0
        if res.falsified:
            stop = "property falsified"
        elif coverage >= threshold:
            stop = "coverage target reached"
        elif prev is not None and coverage <= (prev[1].branch_pct or 0):
            stop = "no coverage gain; remaining branches may be infeasible"
        elif rnd == max_rounds:
            stop = "max rounds"
        else:
            stop = None
        if stop:
            break

        candidate = test_agent.widen(problem, tests, solution, res.branch_pct, threshold,
                                     res.missing_branches)
        changed = _changed(frozen, candidate)
        if changed:                                # one second chance, then give up
            candidate = test_agent.widen(problem, tests, solution, res.branch_pct, threshold,
                                         res.missing_branches, drifted=changed)
            if _changed(frozen, candidate):
                drift, stop = True, "feedback rejected: assert statements changed"
                print(f"   {stop}")
                break
        tests = candidate

    verdict, triage = _verdict(best, threshold), {}
    if verdict == "FALSIFIED":                     # code bug or test bug?
        _, res, final_tests = best
        ref = executor.run(problem.reference, final_tests, pdir / "triage_reference", coverage=False)
        on_ref = {p.test: p.status for p in ref.properties}
        triage = {p.test: on_ref.get(p.test, "TEST_ERROR") for p in res.falsified}
        verdict = "CODE_BUG" if "HOLDS" in triage.values() else "TEST_BUG"

    clean_rounds = [r for r in rounds if r["status"] == "OK"
                    and all(x["status"] != "TEST_ERROR" for x in r["properties"])]
    final = best[1].summary() if best else {"properties": []}
    record = {
        "task_id": problem.task_id, "entry_point": problem.entry_point, "verdict": verdict,
        "rounds_used": len(rounds),
        "first_clean_round": clean_rounds[0]["round"] if clean_rounds else None,
        "final_clean_round": best[0] if best else None,
        "branch_pct_first": clean_rounds[0]["branch_pct"] if clean_rounds else None,
        "branch_pct_final": final.get("branch_pct"),
        "stop_reason": stop,
        "feedback_rejected_for_drift": drift,
        "properties": [{"id": f"P{i}", "text": text, **_result_for(i, final["properties"])}
                       for i, text in enumerate(problem.properties, 1)],
        "triage_on_reference": triage,
        "humaneval_check_passed": executor.humaneval_check(solution, problem.check,
                                                           problem.entry_point, pdir / "humaneval"),
        "rounds": rounds,
    }
    (pdir / "verdict.json").write_text(json.dumps(record, indent=2))
    print(f"   verdict: {verdict} ({stop})")
    return record


def _changed(frozen: dict, candidate: str) -> list[str]:
    now = assertion_fingerprint(candidate)
    if now is None:
        return ["<module does not parse>"]
    return sorted(k for k in set(frozen) | set(now) if frozen.get(k) != now.get(k))


def _result_for(i: int, results: list[dict]) -> dict:
    """Match property Pi to its test by the test_p<i>_ naming convention."""
    return next((r for r in results if r["test"].startswith(f"test_p{i}_")),
                {"test": None, "status": "MISSING"})


def _verdict(best, threshold: float) -> str:
    if best is None:
        return "ERROR"
    res = best[1]
    if res.falsified:
        return "FALSIFIED"
    return "PASS" if (res.branch_pct or 0) >= threshold else "WEAK_PASS"
