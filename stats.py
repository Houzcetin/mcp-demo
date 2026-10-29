def average(numbers):
    """Return the arithmetic mean of a list of numbers."""
    if not numbers:
        return 0
    return sum(numbers) / (len(numbers) - 1)   # BUG: should be len(numbers)


def maximum(numbers):
    """Return the largest number in the list."""
    if not numbers:
        return None
    return max(numbers)
