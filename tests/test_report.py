from datetime import date, datetime, timedelta
from flightwatch.airlines import AirlineTable
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.enrich import enrich
from flightwatch.model import Leg, Segment, Ticket, Trip
from flightwatch.report import render_html, render_email, rank
from flightwatch.shard import Coverage

CFG = load_config()
CAL = DaysOff((), date(2027, 6, 30), date(2027, 9, 15), "https://mon.bg/x")


def s(num, o, d, dep, mins):
    return Segment("TK", num, "Turkish Airlines", o, d, dep, dep + timedelta(minutes=mins), mins, "Boeing 787", "31 in")


def result(total, out_day=5):
    out = Leg((s("1", "SOF", "IST", datetime(2027, 3, out_day, 9, 30), 90),
               s("50", "IST", "NRT", datetime(2027, 3, out_day, 15, 25), 675)), 970, (205,))
    back = Leg((s("51", "NRT", "IST", datetime(2027, 3, out_day + 15, 10), 780),
                s("2", "IST", "SOF", datetime(2027, 3, out_day + 16, 2), 90)), 1050, (180,))
    return enrich(Trip("economy", 4, out, back, (Ticket("TK", (), total, "https://www.google.com/travel/flights/booking?tfs=x"),)),
                  CFG, AirlineTable({}), CAL)


FULL = Coverage(pairs_planned=10, pairs_done=10, requests=20, shards_seen=1, shards_expected=1)


def test_qualifying_first_then_school_days_then_price():
    a, b = result(4600), result(5600)      # €1,150 OK; €1,400 over budget
    assert rank([b, a])[0] is a


def test_html_has_key_facts_and_booking_link():
    html = render_html([result(4400)], FULL, date(2026, 10, 12), {}, CAL.source)
    for text in ["TK50", "IST", "NRT", "€1,100", "€4,400", "31 in", "14 days", "Sofia", "Tokyo",
                 "https://www.google.com/travel/flights/booking?tfs=x", "23 kg"]:
        assert text in html, text


def test_incomplete_coverage_never_says_no_deals():
    cov = Coverage(pairs_planned=10, pairs_done=4, failures=["HTTP 503"], shards_seen=1, shards_expected=1)
    subject, text, _ = render_email([], cov, date(2026, 10, 12), {})
    assert "INCOMPLETE" in subject and "no deals" not in subject.lower()
    assert "40%" in text


def test_complete_and_nothing_under_budget():
    subject, _, _ = render_email([result(5600)], FULL, date(2026, 10, 12), {})
    assert subject.startswith("SOF–TYO: no deals under budget today")
    assert "€1,400" in subject


def test_deals_subject():
    subject, text, html = render_email([result(4400)], FULL, date(2026, 10, 12), {})
    assert subject.startswith("SOF–TYO: 1 deal under budget")
    assert "TK50" in text and "TK50" in html
