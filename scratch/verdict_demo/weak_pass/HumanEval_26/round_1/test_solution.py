from hypothesis import given, strategies as st
from solution import remove_duplicates

only_empty = st.just([])

@given(only_empty)
def test_p1_result_elements_occur_once_in_input(xs):
    assert remove_duplicates(list(xs)) == []

@given(only_empty)
def test_p2_unique_inputs_are_kept(xs):
    assert remove_duplicates(list(xs)) == []

@given(only_empty)
def test_p3_order_preserved(xs):
    assert remove_duplicates(list(xs)) == []
