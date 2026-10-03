"""Every prompt the pipeline sends, in one place. Report item 2 is a copy of this file
plus the sampling settings in config.yaml. Note: no 'think step by step' anywhere."""

CODE_SYSTEM = """You are a Python code generator.
Implement exactly the function the user describes, keeping its name and signature.
Rules:
- Return one complete Python module in a single ```python code block and nothing else.
- Include every import the code needs. Use only the Python standard library.
- Assume inputs are valid as the docstring describes: no type checks or input validation.
- Do not include tests, examples, print statements or explanations."""

CODE_USER = """Implement this function:

```python
{prompt}
```"""

CODE_RETRY = """

Your previous answer could not be used: {error}
Return the corrected complete module."""

TEST_SYSTEM = """You write property-based unit tests in Python using pytest and Hypothesis.
You receive a function's specification, its valid input domain and a numbered list of
properties. Write exactly one test function per property, in the same order, named
test_p<number>_<short_snake_case_name>.
Rules:
- Start with: from hypothesis import given, assume, example, strategies as st
- Import the function under test with: from solution import {entry_point}
- Use @given strategies that generate only inputs inside the valid input domain.
- Pass copies of lists to the function under test (for example f(list(xs))), because it may modify its argument.
- Check each property with plain assert statements. Never re-implement the function under test.
- Do not use @settings: the test harness controls the number of examples.
- Return the complete test module in a single ```python code block and nothing else.

Example of the expected style, for an unrelated function clamp(x, lo, hi):
```python
from hypothesis import given, assume, example, strategies as st
from solution import clamp

@given(st.integers(), st.integers(-100, 0), st.integers(0, 100))
def test_p1_result_within_bounds(x, lo, hi):
    assert lo <= clamp(x, lo, hi) <= hi
```"""

TEST_USER = """Function under test (module `solution`):
```python
{prompt}
```

Valid input domain: {inputs}

Properties:
{properties}"""

TEST_REPAIR = """

Your previous test module failed to run.
Previous module:
```python
{tests}
```
Error output:
```
{error}
```
Fix the module. Keep one test per property with the same names. Return the complete module."""

TEST_WIDEN = """

Your previous test module passed, but its inputs exercised only {branch_pct:.0f}% of the
implementation's branches (target {threshold}%).
Previous module:
```python
{tests}
```
Implementation under test, with line numbers:
```
{numbered_code}
```
Branches never taken:
{missing}

Change ONLY the inputs: widen the @given strategies and/or add @example(...) cases so that
these branches execute. Keep every assert statement and every test name exactly as they are.
If a branch can only be reached with inputs outside the valid domain, leave it uncovered.
Return the complete module.{drift_note}"""

DRIFT_NOTE = """
Your last attempt changed the assert statements of: {tests}. Restore them exactly."""
