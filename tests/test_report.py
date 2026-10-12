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


def test_attachment_is_capped_to_stay_under_email_limits():
    many = [result(4400)] * 600
    html = render_html(many, FULL, date(2026, 10, 12), {}, CAL.source)
    assert html.count("<tr class=") == 500
    assert "best 500 of 600" in html


def test_issue_summary_mentions_owner_and_lists_deals():
    from flightwatch.report import render_issue
    title, body = render_issue([result(4400)], FULL, date(2026, 10, 12), {}, mention="kamenlevi")
    assert title.startswith("SOF–TYO 2026-10-12: 1 deal under budget")
    assert "@kamenlevi" in body and "TK50" in body and "€1,100" in body
    assert "https://www.google.com/travel/flights/booking?tfs=x" in body


def test_issue_for_incomplete_run_says_so():
    from flightwatch.report import render_issue
    cov = Coverage(pairs_planned=10, pairs_done=4, failures=["HTTP 503"], shards_seen=1, shards_expected=1)
    title, body = render_issue([], cov, date(2026, 10, 12), {}, mention="kamenlevi")
    assert "INCOMPLETE" in title and "HTTP 503" in body


def test_rows_show_japan_days_and_trip_day_breakdown():
    from flightwatch.report import render_issue
    r = result(4400)                                    # out Fri 5 Mar, land 6 Mar, leave Tokyo 20 Mar, home 21 Mar
    title, body = render_issue([r], FULL, date(2026, 10, 12), {}, mention="kamenlevi")
    html = render_html([r], FULL, date(2026, 10, 12), {}, CAL.source)
    for text in (body, html):
        assert "14 nights" in text and "13 full days" in text
        assert "17 days away" in text and "11 weekdays" in text and "6 weekend days" in text



def test_december_trips_are_recommended_and_ranked_first():
    from flightwatch.report import render_issue
    march = result(4000)                                     # €1,000 pp, March
    dec = result(4600, out_day=5)
    dec = enrich(replace_dates(dec.trip, 2026, 12), CFG, AirlineTable({}), CAL)   # €1,150 pp, December
    assert dec.december_pick and not march.december_pick
    assert rank([march, dec])[0] is dec
    title, body = render_issue([march, dec], FULL, date(2026, 10, 12), {}, mention="kamenlevi")
    assert "December pick" in body and "December" in title


def replace_dates(trip, year, month):
    from dataclasses import replace as rp
    def leg(l):
        return rp(l, segments=tuple(rp(s, dep=s.dep.replace(year=year, month=month), arr=s.arr.replace(year=year, month=month))
                                    for s in l.segments))
    return rp(trip, outbound=leg(trip.outbound), inbound=leg(trip.inbound))
