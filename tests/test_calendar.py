from datetime import date, timedelta
from flightwatch.calendar_bg import DaysOff

CAL = DaysOff.load()


def test_weekends_and_christmas_break_are_off_but_early_december_is_school():
    assert CAL.is_off(date(2027, 2, 13))          # Saturday
    assert not CAL.is_off(date(2026, 12, 14))     # an ordinary Monday: December is a school month again
    assert all(CAL.is_off(date(2026, 12, d)) for d in range(24, 32))   # Christmas break


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
    assert CAL.school_days_missed(date(2026, 12, 5), date(2026, 12, 22)) == 12   # 7–11, 14–18, 21–22 Dec


def test_next_school_year_counts_school_days_again():
    assert not CAL.is_off(date(2027, 9, 20))       # a Monday in the 2027/28 school year
    assert CAL.is_off(date(2027, 8, 16))           # summer holiday


def test_breakdown_of_a_christmas_trip():
    b = CAL.breakdown(date(2026, 12, 13), date(2027, 1, 1))
    assert (b.total, b.weekdays, b.weekend, b.school_days) == (20, 15, 5, 8)   # Sun 13 Dec to Fri 1 Jan; school 14–18, 21–23
    names = [name for _, name in b.holidays]
    assert "Christmas" in " ".join(names) and "New Year" in " ".join(names)


def test_holidays_listed_from_pochivnidni():
    assert any(d == date(2027, 3, 3) for d, _ in CAL.holidays)
    assert any(d == date(2027, 5, 2) for d, _ in CAL.holidays)        # Easter 2027
