from flightwatch.seating import plan_seats


def test_787_economy_four_is_two_plus_two_across_aisle():
    p = plan_seats("3-3-3", 4)
    assert p.groups == (2, 2) and p.seats == ("B", "C", "D", "E")


def test_three_take_a_window_block():
    p = plan_seats("3-3-3", 3)
    assert p.groups == (3,) and p.seats == ("A", "B", "C") and p.windows == 1


def test_middle_four_block_on_2_4_2():
    assert plan_seats("2-4-2", 4).seats == ("D", "E", "F", "G")


def test_premium_2_3_2_three_together_in_middle():
    assert plan_seats("2-3-2", 3).groups == (3,)


def test_premium_2_2_2_three_is_two_plus_one():
    assert plan_seats("2-2-2", 3).groups == (2, 1)


def test_narrowbody_four():
    assert plan_seats("3-3", 4).groups == (2, 2)


def test_unknown_layout():
    assert plan_seats("weird", 4) is None
