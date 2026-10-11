import base64
from urllib.parse import urlparse, parse_qs
from fast_flights.pb.flights_pb2 import Info
from flightwatch.google.query import LegQuery, SelectedSegment, encode_selected, build_params, booking_url

LOT632 = SelectedSegment("SOF", "2026-12-19", "WAW", "LO", "632")


def test_selected_segment_bytes_match_what_google_accepted_in_the_spike():
    # Hex recorded on 2026-10-11 from the request that made Google return LOT's matching returns
    assert encode_selected(LOT632).hex() == (
        "221f0a03534f46120a323032362d31322d31391a035741572a024c4f3203363332")


def test_round_trip_params_decode_to_two_legs_with_filters():
    p = build_params([LegQuery("2026-12-19", "SOF", "TYO"), LegQuery("2027-01-03", "TYO", "SOF")],
                     "premium-economy", 4, 1, 1200, 1)
    assert p["hl"] == "en" and p["curr"] == "EUR"
    info = Info()
    info.ParseFromString(base64.b64decode(p["tfs"]))
    assert [d.date for d in info.data] == ["2026-12-19", "2027-01-03"]
    assert [d.from_airport.airport for d in info.data] == ["SOF", "TYO"]
    assert all(d.max_stops == 1 and d.max_duration_minutes == 1200 for d in info.data)
    assert len(info.passengers) == 4
    assert info.baggage.checked_bags == 1


def test_selected_segments_survive_serialisation():
    p = build_params([LegQuery("2026-12-19", "SOF", "TYO", (LOT632,)), LegQuery("2027-01-03", "TYO", "SOF")],
                     "economy", 4, 1, None, 1)
    raw = base64.b64decode(p["tfs"])
    assert encode_selected(LOT632) in raw


def test_booking_url_points_at_google_booking_page():
    p = build_params([LegQuery("2026-12-19", "SOF", "TYO")], "economy", 4, 1, None, 1)
    u = urlparse(booking_url(p))
    assert u.netloc == "www.google.com" and u.path == "/travel/flights/booking"
    assert parse_qs(u.query)["tfs"] == [p["tfs"]]
