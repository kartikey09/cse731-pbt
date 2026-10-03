"""Day 3: turn a run folder into report material.

Writes results.md (main table), results.csv, coverage.png, mutation.png and
prompts_appendix.md (report item 2: prompts + settings, pulled from llm_log.jsonl).
Usage: python tools/summarize.py runs/<name>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def bars(path: Path, labels, first, final, ylabel: str, title: str) -> None:
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.8), 3.6))
    ax.bar([i - 0.2 for i in x], first, width=0.4, label="first clean tests", color="#9aa5b1")
    ax.bar([i + 0.2 for i in x], final, width=0.4, label="after coverage feedback", color="#2f6f73")
    ax.set_xticks(list(x), labels, rotation=35, ha="right")
    ax.set_ylim(0, 122)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main(run: Path) -> None:
    verdicts = [json.loads(f.read_text()) for f in sorted(run.glob("*/verdict.json"),
                                                          key=lambda f: int(f.parent.name.split("_")[-1]))]
    mutation = {}
    if (run / "mutation.json").exists():
        mutation = {r["task_id"]: r for r in json.loads((run / "mutation.json").read_text())}

    rows = []
    for v in verdicts:
        m = mutation.get(v["task_id"], {})
        held = sum(p["status"] == "HOLDS" for p in v["properties"])
        bugs = [f'{p["id"]}: {p["counterexample"]}' for p in v["properties"] if p["status"] == "FALSIFIED"]
        rows.append({
            "task": v["task_id"], "function": v["entry_point"], "verdict": v["verdict"],
            "properties_held": f"{held}/{len(v['properties'])}",
            "branch_first": v["branch_pct_first"], "branch_final": v["branch_pct_final"],
            "rounds": v["rounds_used"], "stop_reason": v["stop_reason"],
            "humaneval_check": v["humaneval_check_passed"],
            "mutation_first": m.get("first", {}).get("score"),
            "mutation_final": m.get("final", {}).get("score"),
            "counterexamples": " | ".join(bugs)})

    with (run / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    head = ("| Task | Function | Verdict | Properties held | Branch cov. first → final | Rounds "
            "| HumanEval check | Mutation score first → final |\n|---|---|---|---|---|---|---|---|\n")
    body = "".join(
        f"| {r['task']} | `{r['function']}` | {r['verdict']} | {r['properties_held']} | "
        f"{r['branch_first']} → {r['branch_final']} | {r['rounds']} | "
        f"{'pass' if r['humaneval_check'] else 'fail'} | {r['mutation_first']} → {r['mutation_final']} |\n"
        for r in rows)
    counts = Counter(r["verdict"] for r in rows)
    falsified = "".join(f"- {r['task']} `{r['function']}`: {r['counterexamples']}\n"
                        for r in rows if r["counterexamples"])
    (run / "results.md").write_text(
        f"# Results for run `{run.name}`\n\nVerdicts: {dict(counts)}\n\n{head}{body}\n"
        f"## Counterexamples found\n\n{falsified or 'none'}\n")

    labels = [r["function"] for r in rows]
    bars(run / "coverage.png", labels, [r["branch_first"] or 0 for r in rows],
         [r["branch_final"] or 0 for r in rows], "branch coverage (%)", "Branch coverage per unit")
    if mutation:
        ok = [r for r in rows if r["mutation_first"] is not None]
        bars(run / "mutation.png", [r["function"] for r in ok], [r["mutation_first"] for r in ok],
             [r["mutation_final"] for r in ok], "mutants killed (%)", "Mutation score per unit")

    log = [json.loads(line) for line in (run / "llm_log.jsonl").read_text().splitlines()]
    parts = [f"# Prompts and settings (run `{run.name}`)\n",
             f"Model calls: {len(log)} ({sum(not e['cached'] for e in log)} live, "
             f"{sum(e['cached'] for e in log)} from cache). Models: "
             f"{sorted({e['served_model'] or e['model'] for e in log})}\n"]
    fence = "````"  # four backticks, because the prompts themselves contain ``` blocks
    for agent in sorted({e["agent"] for e in log}):
        calls = [e for e in log if e["agent"] == agent]
        first = calls[0]
        parts.append(f"\n## Agent `{agent}` ({len(calls)} calls)\n\n"
                     f"Settings: `{json.dumps(first['params'])}`\n\n"
                     f"System prompt:\n\n{fence}text\n{first['system']}\n{fence}\n\n"
                     f"Example user prompt:\n\n{fence}text\n{first['user']}\n{fence}\n\n"
                     f"Example response:\n\n{fence}text\n{first['response']}\n{fence}\n")
    (run / "prompts_appendix.md").write_text("".join(parts))
    print(f"wrote results.md, results.csv, coverage.png, prompts_appendix.md"
          f"{', mutation.png' if mutation else ''} in {run}/")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
