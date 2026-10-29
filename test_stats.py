from stats import average, maximum


def test_average():
    assert average([2, 4, 6]) == 4


def test_average_empty():
    assert average([]) == 0


def test_maximum():
    assert maximum([3, 9, 1]) == 9
