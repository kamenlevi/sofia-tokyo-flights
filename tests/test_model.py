from datetime import datetime
from flightwatch.model import Segment, Leg, Ticket, Trip, trip_to_dict, trip_from_dict


def seg(code, o, d, dep, arr, mins):
    return Segment(code[:2], code[2:], "Airline", o, d, dep, arr, mins, "Boeing 787", "31 in")


def sample_trip(party=4, total=4400):
    out = Leg((seg("TK1028", "SOF", "IST", datetime(2027, 3, 5, 9, 30), datetime(2027, 3, 5, 12, 0), 90),
               seg("TK50", "IST", "NRT", datetime(2027, 3, 5, 15, 25), datetime(2027, 3, 6, 8, 40), 675)),
              970, (205,))
    back = Leg((seg("TK51", "NRT", "IST", datetime(2027, 3, 20, 10, 0), datetime(2027, 3, 20, 17, 0), 780),
                seg("TK1027", "IST", "SOF", datetime(2027, 3, 20, 19, 0), datetime(2027, 3, 20, 20, 30), 90)),
               1050, (120,))
    return Trip("economy", party, out, back,
                (Ticket("TK", ("TK1028", "TK50", "TK51", "TK1027"), total, "https://example/book"),))


def test_trip_derived_values():
    t = sample_trip()
    assert t.total_eur == 4400
    assert t.per_person_eur == 1100
    assert t.stay_days == 14            # lands 6 Mar, leaves Tokyo 20 Mar
    assert not t.self_transfer
    assert t.outbound.key == "TK1028@2027-03-05+TK50@2027-03-05"


def test_round_trip_serialisation():
    t = sample_trip()
    assert trip_from_dict(trip_to_dict(t)) == t
