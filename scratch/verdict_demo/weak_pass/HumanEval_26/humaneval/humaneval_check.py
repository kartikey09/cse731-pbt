def remove_duplicates(numbers):
    seen, dupes = set(), set()
    for n in numbers:
        if n in seen:
            dupes.add(n)
        else:
            seen.add(n)
    result = []
    for n in numbers:
        if n not in dupes:
            result.append(n)
    return result




METADATA = {
    'author': 'jt',
    'dataset': 'test'
}


def check(candidate):
    assert candidate([]) == []
    assert candidate([1, 2, 3, 4]) == [1, 2, 3, 4]
    assert candidate([1, 2, 3, 2, 4, 3, 5]) == [1, 4, 5]


check(remove_duplicates)
