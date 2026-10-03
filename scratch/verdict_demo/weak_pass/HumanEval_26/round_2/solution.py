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
