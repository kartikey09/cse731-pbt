"""First-order mutants of a HumanEval reference solution (Day 3 evaluation).

Each mutant changes exactly one operator, constant or if-condition. A strong test suite
fails ("kills") most of them. Mutation score = killed / total.
"""
from __future__ import annotations

import ast
import copy
import random

CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
       ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In}
BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult,
       ast.Mod: ast.FloorDiv}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}
SYMBOL = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
          ast.In: "in", ast.NotIn: "not in", ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
          ast.FloorDiv: "//", ast.Mod: "%", ast.And: "and", ast.Or: "or"}


def _sites(tree: ast.AST):
    for i, node in enumerate(ast.walk(tree)):
        if isinstance(node, ast.Compare):
            for j, op in enumerate(node.ops):
                if type(op) in CMP:
                    yield i, "cmp", j
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN:
            yield i, "bin", None
        elif isinstance(node, ast.BoolOp) and type(node.op) in BOOL:
            yield i, "bool", None
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            yield i, "int", None
        elif isinstance(node, ast.If):
            yield i, "if", None


def _apply(tree: ast.AST, index: int, kind: str, j: int | None) -> str:
    node = list(ast.walk(tree))[index]
    line = f"line {node.lineno}"
    if kind == "cmp":
        old = type(node.ops[j])
        node.ops[j] = CMP[old]()
        return f"{line}: {SYMBOL[old]} -> {SYMBOL[CMP[old]]}"
    if kind in ("bin", "bool"):
        table = BIN if kind == "bin" else BOOL
        old = type(node.op)
        node.op = table[old]()
        return f"{line}: {SYMBOL[old]} -> {SYMBOL[table[old]]}"
    if kind == "int":
        node.value += 1
        return f"{line}: {node.value - 1} -> {node.value}"
    node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    return f"{line}: if-condition negated"


def make_mutants(source: str, limit: int = 12, seed: int = 0) -> list[dict]:
    tree = ast.parse(source)
    seen, mutants = {ast.unparse(tree)}, []
    for index, kind, j in _sites(tree):
        mutated = copy.deepcopy(tree)
        change = _apply(mutated, index, kind, j)
        code = ast.unparse(ast.fix_missing_locations(mutated))
        if code not in seen:
            seen.add(code)
            mutants.append({"change": change, "source": code})
    random.Random(seed).shuffle(mutants)
    chosen = mutants[:limit]
    for k, m in enumerate(chosen, 1):
        m["id"] = f"m{k:02d}"
    return chosen
