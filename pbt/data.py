"""HumanEval problems joined with the user's property spec."""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Problem:
    task_id: str
    entry_point: str
    prompt: str        # imports + signature + docstring: the specification both LLM agents see
    reference: str     # prompt + canonical solution: used only to triage failures
    check: str         # HumanEval's hidden tests: used only for evaluation on Day 3
    inputs: str        # user-specified valid input domain
    properties: list[str] = field(default_factory=list)  # user-specified properties

    @property
    def slug(self) -> str:
        return self.task_id.replace("/", "_")


def load_problems(dataset: str, properties_file: str, only: list[str] | None = None) -> list[Problem]:
    rows = {}
    with gzip.open(dataset, "rt") as f:
        for line in f:
            row = json.loads(line)
            rows[row["task_id"]] = row
    problems = []
    for item in yaml.safe_load(Path(properties_file).read_text()):
        if only and item["task_id"] not in only:
            continue
        row = rows[item["task_id"]]
        problems.append(Problem(
            task_id=row["task_id"], entry_point=row["entry_point"], prompt=row["prompt"],
            reference=row["prompt"] + row["canonical_solution"], check=row["test"],
            inputs=item.get("inputs", ""), properties=list(item["properties"])))
    return problems
