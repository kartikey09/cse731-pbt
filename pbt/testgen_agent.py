"""Agent 2, Test Generator: specification + user properties -> Hypothesis property tests."""
from __future__ import annotations

import ast
import builtins
import copy

from . import prompts
from .codegen_agent import extract_code


class _Canon(ast.NodeTransformer):
    """Rename local variables to v0, v1, ... so renaming a variable is not seen as a change."""

    def __init__(self, keep: set[str]):
        self.keep, self.names = keep, {}

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.keep:
            return node
        new_id = self.names.setdefault(node.id, f"v{len(self.names)}")
        return ast.copy_location(ast.Name(id=new_id, ctx=node.ctx), node)


def assertion_fingerprint(test_src: str) -> dict[str, list[str]] | None:
    """{test name: [normalised assert statements]}. Coverage feedback may change how inputs
    are generated, never what is asserted, so this must not change once tests run cleanly."""
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        return None
    keep = set(dir(builtins))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            keep.add(node.name)
    prints = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            canon = _Canon(keep)
            prints[node.name] = [ast.unparse(canon.visit(copy.deepcopy(a)))
                                 for a in ast.walk(node) if isinstance(a, ast.Assert)]
    return prints


def number_lines(src: str) -> str:
    return "\n".join(f"{i:>3}| {line}" for i, line in enumerate(src.splitlines(), 1))


def describe_missing(src: str, missing: list[list[int]]) -> str:
    lines = src.splitlines()

    def at(n: int) -> str:
        return lines[n - 1].strip() if 0 < n <= len(lines) else "?"

    return "\n".join(
        f"- line {a} `{at(a)}` -> " + ("exit the function" if b < 0 else f"line {b} `{at(b)}`")
        for a, b in missing)


class TestGenAgent:
    name = "test_gen"
    __test__ = False  # tell pytest this class is not a test

    def __init__(self, llm, params: dict):
        self.llm, self.params = llm, params

    def _spec(self, problem) -> str:
        props = "\n".join(f"P{i}. {p}" for i, p in enumerate(problem.properties, 1))
        return prompts.TEST_USER.format(prompt=problem.prompt, inputs=problem.inputs, properties=props)

    def _ask(self, problem, user: str) -> str:
        system = prompts.TEST_SYSTEM.format(entry_point=problem.entry_point)
        return extract_code(self.llm.chat(self.name, system, user, self.params))

    def generate(self, problem) -> str:
        return self._ask(problem, self._spec(problem))

    def repair(self, problem, tests: str, error: str) -> str:
        return self._ask(problem, self._spec(problem) + prompts.TEST_REPAIR.format(
            tests=tests, error=error[-2500:]))

    def widen(self, problem, tests: str, solution: str, branch_pct: float, threshold: float,
              missing: list[list[int]], drifted: list[str] | None = None) -> str:
        note = prompts.DRIFT_NOTE.format(tests=", ".join(drifted)) if drifted else ""
        return self._ask(problem, self._spec(problem) + prompts.TEST_WIDEN.format(
            branch_pct=branch_pct, threshold=threshold, tests=tests,
            numbered_code=number_lines(solution), missing=describe_missing(solution, missing),
            drift_note=note))
