"""Hand-written property tests for HumanEval/26 remove_duplicates (Day 1, Member B).
The executor saves this as test_solution.py, next to the code under test."""
from collections import Counter

from hypothesis import given, strategies as st

from solution import remove_duplicates

numbers = st.lists(st.integers(-5, 5), max_size=20)  # small range: repeats are common


@given(numbers)
def test_p1_result_elements_occur_once_in_input(xs):
    counts = Counter(xs)
    assert all(counts[x] == 1 for x in remove_duplicates(list(xs)))


@given(numbers)
def test_p2_unique_inputs_are_kept(xs):
    result = remove_duplicates(list(xs))
    assert all(x in result for x, k in Counter(xs).items() if k == 1)


@given(numbers)
def test_p3_order_preserved(xs):
    result = remove_duplicates(list(xs))
    remaining = iter(xs)
    assert all(any(x == y for y in remaining) for x in result)
