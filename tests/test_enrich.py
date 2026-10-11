from datetime import datetime, timedelta, date
from flightwatch.airlines import AirlineTable, Airline
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.enrich import enrich
from flightwatch.model import Leg, Segment, Ticket, Trip

CFG = load_config()
CAL = DaysOff((), date(2027, 6, 30), date(2027, 9, 15), "test")


def s(carrier, num, o, d, dep, mins, aircraft="Boeing 787"):
    return Segment(carrier, num, carrier, o, d, dep, dep + timedelta(minutes=mins), mins, aircraft, "31 in")


def trip(carrier="ZZ", feeder="ZZ"):
    out = Leg((s(feeder, "1", "SOF", "IST", datetime(2027, 3, 5, 9, 0), 150, "A320"),
               s(carrier, "50", "IST", "NRT", datetime(2027, 3, 5, 14, 30), 675)), 1005, (180,))
    back = Leg((s(carrier, "51", "NRT", "IST", datetime(2027, 3, 20, 10, 0), 780),
                s(feeder, "2", "IST", "SOF", datetime(2027, 3, 20, 20, 0), 150, "A320")), 1240, (180,))
    return Trip("economy", 4, out, back, (Ticket(carrier, (), 4000, "https://g/booking"),))


def test_unknown_airline_is_not_verified_but_kept():
    r = enrich(trip(), CFG, AirlineTable({}), CAL)
    assert all(v.meals == "not verified" for v in r.outbound + r.inbound)
    assert r.trip is not None and r.price_pp == 1000


def test_paid_meals_add_to_price():
    table = AirlineTable({"PC": Airline("PC", "Pegasus", "https://flypgs.com", "paid", "paid", 12.0, None, None, None,
                                        "https://flypgs.com/x", "2026-10-12", ())})
    r = enrich(trip(feeder="PC"), CFG, table, CAL)
    assert r.meal_addon_pp == 24.0                 # two 150-minute PC flights, €12 each
    assert r.price_pp == 1024.0


def test_school_days_and_recommended():
    r = enrich(trip(), CFG, AirlineTable({}), CAL)
    assert r.recommended                           # 14 days
    assert r.school_days == 11                     # Fri 5, 8–12, 15–19 Mar; home Sat 20 Mar
