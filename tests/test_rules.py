from dataclasses import replace
from datetime import datetime, timedelta
from flightwatch.config import load_config
from flightwatch.model import Leg, Ticket, Trip, Segment
from flightwatch.rules import check, structural_problems

CFG = load_config()


def s(code, o, d, dep, mins):
    return Segment(code[:2], code[2:], "A", o, d, dep, dep + timedelta(minutes=mins), mins, "787", "31 in")


def leg(*segs):
    lay = tuple(int((b.dep - a.arr).total_seconds() // 60) for a, b in zip(segs, segs[1:]))
    return Leg(segs, int((segs[-1].arr - segs[0].dep).total_seconds() // 60), lay)


OUT = leg(s("TK1", "SOF", "IST", datetime(2027, 3, 5, 9, 30), 90), s("TK50", "IST", "NRT", datetime(2027, 3, 5, 15, 25), 675))
BACK = leg(s("TK51", "NRT", "IST", datetime(2027, 3, 20, 10, 0), 780), s("TK2", "IST", "SOF", datetime(2027, 3, 21, 2, 0), 90))
# lands IST 23:00, leaves 02:00: 3 h, so it also passes as a self-transfer


def trip(out=OUT, back=BACK, total=4400, tickets=None, cabin="economy"):
    return Trip(cabin, 4, out, back, tickets or (Ticket("TK", (), total, "u"),))


def test_good_trip_passes():
    assert check(trip(), CFG) == []


def test_over_20_hours_rejected():
    long_out = leg(s("LO1", "SOF", "WAW", datetime(2027, 3, 5, 6, 0), 120), s("LO79", "WAW", "NRT", datetime(2027, 3, 5, 16, 0), 660))
    assert any("20h" in p for p in check(trip(out=long_out), CFG))   # 06:00 to 03:00 next day is 21h


def test_three_flights_rejected():
    three = leg(s("A1", "SOF", "VIE", datetime(2027, 3, 5, 6, 0), 90), s("A2", "VIE", "FRA", datetime(2027, 3, 5, 8, 0), 60),
                s("A3", "FRA", "HND", datetime(2027, 3, 5, 10, 0), 600))
    assert any("flights" in p for p in check(trip(out=three), CFG))


def test_stay_bounds():
    short_back = leg(*(replace(x, dep=x.dep - timedelta(days=6), arr=x.arr - timedelta(days=6)) for x in BACK.segments))
    assert any("stay" in p for p in check(trip(back=short_back), CFG))   # 8 days


def test_budget_per_cabin_and_addons():
    assert check(trip(total=4800), CFG) == []                              # €1,200 exactly is fine
    assert any("budget" in p for p in check(trip(total=4800), CFG, addon_pp=5))
    assert check(trip(total=5200, cabin="premium-economy"), CFG) == []


def test_self_transfer_needs_three_hours():
    tight = leg(s("FB1", "SOF", "IST", datetime(2027, 3, 5, 9, 0), 90), s("TK50", "IST", "NRT", datetime(2027, 3, 5, 13, 0), 675))
    tickets = (Ticket("FB", ("FB1",), 400, "u"), Ticket("TK", ("TK50",), 3600, "u"))
    assert any("self-transfer" in p for p in structural_problems(trip(out=tight, tickets=tickets), CFG))   # 150 min
    ok = leg(s("FB1", "SOF", "IST", datetime(2027, 3, 5, 9, 0), 90), s("TK50", "IST", "NRT", datetime(2027, 3, 5, 13, 30), 675))
    assert structural_problems(trip(out=ok, tickets=tickets), CFG) == []


def test_must_land_in_tokyo():
    osaka = leg(s("TK1", "SOF", "IST", datetime(2027, 3, 5, 9, 30), 90), s("TK86", "IST", "KIX", datetime(2027, 3, 5, 15, 25), 660))
    assert any("Tokyo" in p for p in check(trip(out=osaka), CFG))


def test_premium_economy_search_with_economy_long_haul_uses_economy_budget():
    pe_out = Leg(tuple(replace(x, cabin=2) for x in OUT.segments), OUT.minutes, OUT.layovers)
    eco_back = Leg(tuple(replace(x, cabin=1) for x in BACK.segments), BACK.minutes, BACK.layovers)
    probs = check(trip(out=pe_out, back=eco_back, total=5000, cabin="premium-economy"), CFG)   # €1,250 pp
    assert any("economy" in p and "budget" in p for p in probs)
    pe_back = Leg(tuple(replace(x, cabin=2) for x in BACK.segments), BACK.minutes, BACK.layovers)
    assert check(trip(out=pe_out, back=pe_back, total=5000, cabin="premium-economy"), CFG) == []
