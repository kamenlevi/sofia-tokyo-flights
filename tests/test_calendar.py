from datetime import date, timedelta
from flightwatch.calendar_bg import DaysOff

CAL = DaysOff.load()


def test_weekends_and_all_of_december_are_off():
    assert CAL.is_off(date(2027, 2, 13))          # Saturday
    assert all(CAL.is_off(date(2026, 12, d)) for d in range(1, 32))


def test_after_school_year_everything_is_off():
    assert CAL.is_off(date(2027, 7, 15))


def test_known_dates():
    assert CAL.is_off(date(2027, 3, 3))           # Liberation Day (a Wednesday)
    assert CAL.is_off(date(2027, 5, 6))           # St George's Day (a Thursday)
    assert not CAL.is_off(date(2026, 11, 11))     # an ordinary Wednesday; confirm against the order


def test_school_days_missed_counts_inclusive_weekdays_not_off():
    # Both ends count: leaving on a school day or landing home on one still misses it
    first, last = date(2027, 3, 5), date(2027, 3, 20)
    expected = sum(1 for i in range(16) if not CAL.is_off(first + timedelta(days=i)))
    assert CAL.school_days_missed(first, last) == expected
    assert CAL.school_days_missed(date(2027, 3, 5), date(2027, 3, 5)) == (0 if CAL.is_off(date(2027, 3, 5)) else 1)
    assert CAL.school_days_missed(date(2026, 12, 5), date(2026, 12, 22)) == 0


def test_next_school_year_counts_school_days_again():
    assert not CAL.is_off(date(2027, 9, 20))       # a Monday in the 2027/28 school year
    assert CAL.is_off(date(2027, 8, 16))           # summer holiday
