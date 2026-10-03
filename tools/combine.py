"""Combine the generated / seeded / reference runs into one side-by-side table.

    python -m tools.combine [--runs runs] [--out runs/combined.md]

Reads each run's per-unit verdict.json, so it needs no network and no LLM.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

RUNS = [
    ("generated", "day2_full"),
    ("seeded", "seeded"),
    ("reference", "reference"),
]


def load(run_dir: Path) -> dict:
    out = {}
    for f in sorted(run_dir.glob("HumanEval_*/verdict.json")):
        v = json.loads(f.read_text())
        out[v["task_id"]] = v
    return out


def task_key(task_id: str) -> int:
    return int(task_id.split("/")[1])


def cell(v: dict | None) -> str:
    if v is None:
        return "–"
    props = v.get("properties", [])
    held = sum(p["status"] == "HOLDS" for p in props)
    return f"{v['verdict']} ({held}/{len(props)})"


def build(runs_dir: Path) -> str:
    data = {label: load(runs_dir / name) for label, name in RUNS}
    tasks = sorted({t for d in data.values() for t in d}, key=task_key)
    entry = {t: next(d[t]["entry_point"] for d in data.values() if t in d) for t in tasks}
    bug = {t: data["seeded"].get(t, {}).get("seeded_bug", "") for t in tasks}

    lines = ["# Combined results: generated vs seeded vs reference", ""]
    lines += ["Each cell is `VERDICT (properties held/total)`.", ""]
    lines += ["| Task | Function | Generated code | Seeded bug | Seeded verdict | Reference code |",
              "|---|---|---|---|---|---|"]
    for t in tasks:
        lines.append(
            f"| {t} | `{entry[t]}` | {cell(data['generated'].get(t))} | {bug[t]} | "
            f"{cell(data['seeded'].get(t))} | {cell(data['reference'].get(t))} |")

    lines += ["", "## Verdict totals", "",
              "| Run | Code under test | " + " | ".join(
                  ["PASS", "WEAK_PASS", "CODE_BUG", "TEST_BUG", "ERROR"]) + " |",
              "|---|---|---|---|---|---|---|"]
    desc = {"generated": "LLM-generated", "seeded": "hand-planted bugs",
            "reference": "HumanEval canonical"}
    for label, _ in RUNS:
        c = Counter(v["verdict"] for v in data[label].values())
        lines.append(f"| {label} | {desc[label]} | " + " | ".join(
            str(c.get(k, 0)) for k in ["PASS", "WEAK_PASS", "CODE_BUG", "TEST_BUG", "ERROR"]) + " |")

    # Seeded-run reading: what the executor got right or missed.
    caught = [t for t in tasks if data["seeded"].get(t, {}).get("verdict") == "CODE_BUG"]
    missed = [t for t in tasks if data["seeded"].get(t, {}).get("verdict") == "PASS"]
    tb = [t for t in tasks if data["seeded"].get(t, {}).get("verdict") == "TEST_BUG"]
    lines += ["", "## Reading the seeded run", "",
              f"- Bug caught (`CODE_BUG`): {len(caught)}/{len(tasks)}",
              f"- Bug missed (`PASS`): {', '.join(f'{entry[t]}' for t in missed) or 'none'}"
              " — the properties are too weak to see it",
              f"- `TEST_BUG`: {', '.join(f'{entry[t]}' for t in tb) or 'none'}"
              " — fails on the reference too, so the property is wrong, not the code"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("/Users/ranag/cse731-pbt/runs"))
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    md = build(a.runs)
    out = a.out or a.runs / "combined.md"
    out.write_text(md)
    print(md)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
