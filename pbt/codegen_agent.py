"""Agent 1, Code Generator: HumanEval specification -> solution.py"""
from __future__ import annotations

import ast
import re
import subprocess
import sys

from . import prompts

FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S)


def extract_code(reply: str) -> str:
    """Take the longest fenced code block; fall back to the raw reply."""
    blocks = FENCE.findall(reply)
    return (max(blocks, key=len) if blocks else reply).strip() + "\n"


def check_module(src: str, entry_point: str) -> str | None:
    """None if src parses, imports cleanly and defines entry_point; otherwise the reason."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"SyntaxError: {e}"
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if entry_point not in defined:
        return f"the module does not define a top-level function named {entry_point}"
    try:  # executes only the module's top level (imports, defs) in a separate process
        p = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return "importing the module did not finish within 10 seconds"
    if p.returncode != 0:
        return "importing the module failed: " + p.stderr.strip().splitlines()[-1]
    return None


class CodeGenAgent:
    name = "code_gen"

    def __init__(self, llm, params: dict):
        self.llm, self.params = llm, params

    def run(self, problem) -> str:
        user = prompts.CODE_USER.format(prompt=problem.prompt)
        error = None
        for _ in range(2):  # one retry with the error message
            text = user if error is None else user + prompts.CODE_RETRY.format(error=error)
            src = extract_code(self.llm.chat(self.name, prompts.CODE_SYSTEM, text, self.params))
            error = check_module(src, problem.entry_point)
            if error is None:
                return src
        raise RuntimeError(f"{problem.task_id}: code generator failed twice: {error}")
