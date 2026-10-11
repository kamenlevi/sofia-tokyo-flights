from datetime import datetime
from pathlib import Path
import re
import pytest
from googlefake import seg, itin, page, CONSENT
from flightwatch.google.parse import parse_options, ConsentPageError, GoogleFormatError
from flightwatch.google.query import SelectedSegment

FIX = Path(__file__).parent / "fixtures"

OVERNIGHT = itin("TK", [
    seg("SOF", "IST", [2026, 11, 28], [21, 40], [2026, 11, 29], [None, 10], 90, "TK", "1030"),
    seg("IST", "HND", [2026, 11, 29], [2, 30], [2026, 11, 29], [19, 45], 675, "TK", "198"),
], 905, [140], 3185)


def test_overnight_and_dropped_zero_times():
    [o] = parse_options(page([OVERNIGHT]))
    a, b = o.leg.segments
    assert a.dep == datetime(2026, 11, 28, 21, 40)
    assert a.arr == datetime(2026, 11, 29, 0, 10)       # [None, 10] means 00:10
    assert b.arr == datetime(2026, 11, 29, 19, 45)
    assert o.leg.minutes == 905 and o.leg.layovers == (140,)
    assert o.total_eur == 3185 and o.seller == "TK"
    assert a.legroom == "31 in" and a.code == "TK1030"


def test_hour_only_time():
    x = itin("LO", [seg("NRT", "WAW", [2027, 1, 3], [23], [2027, 1, 4], [5, 45], 780, "LO", "80")], 780, [], 900)
    [o] = parse_options(page([x]))
    assert o.leg.dep == datetime(2027, 1, 3, 23, 0)


def test_priceless_itinerary_is_kept_with_none_and_both_sections_read():
    sold_out = itin("LO", [seg("SOF", "WAW", [2026, 12, 19], [14, 35], [2026, 12, 19], [15, 35], 120, "LO", "632")],
                    120, [], None)
    opts = parse_options(page([OVERNIGHT], [sold_out]))
    assert [o.total_eur for o in opts] == [3185, None]


def test_duplicate_itinerary_keeps_lowest_price():
    cheaper = itin("TK", OVERNIGHT[0][2], 905, [140], 3000)
    [o] = parse_options(page([OVERNIGHT], [cheaper]))
    assert o.total_eur == 3000


def test_no_flights_page_is_empty_list():
    assert parse_options(page([])) == []


def test_consent_page_raises():
    with pytest.raises(ConsentPageError):
        parse_options(CONSENT)


def test_changed_layout_raises_format_error():
    with pytest.raises(GoogleFormatError):
        parse_options("<html><body>totally different</body></html>")


def test_selected_segments_for_pairing():
    [o] = parse_options(page([OVERNIGHT]))
    assert o.selected() == (SelectedSegment("SOF", "2026-11-28", "IST", "TK", "1030"),
                            SelectedSegment("IST", "2026-11-29", "HND", "TK", "198"))


@pytest.mark.parametrize("name", ["stage1_rt.html", "stage2_rt.html", "feeder_oneway.html"])
def test_recorded_fixtures_parse(name):
    opts = parse_options((FIX / name).read_text())
    assert opts, f"{name} parsed to nothing"
    for o in opts:
        assert 1 <= len(o.leg.segments) <= 2
        assert o.leg.minutes > 0
        for s in o.leg.segments:
            assert re.fullmatch(r"[A-Z0-9]{2}", s.carrier) and s.number
            assert s.arr > s.dep or s.arr.date() >= s.dep.date()


def test_cabin_per_segment():
    x = itin("LH", [seg("SOF", "MUC", [2027, 3, 5], [6], [2027, 3, 5], [7], 125, "LH", "1703", cabin=1),
                    seg("MUC", "HND", [2027, 3, 5], [10], [2027, 3, 6], [7], 750, "NH", "218", cabin=2)], 1500, [180], 9000)
    [o] = parse_options(page([x]))
    assert [s.cabin for s in o.leg.segments] == [1, 2]


def test_page_where_no_option_has_a_price_still_parses():
    # Google does list sold-out premium economy itineraries without prices; one such page is normal
    nop = itin("TK", OVERNIGHT[0][2], 905, [140], None)
    assert [o.total_eur for o in parse_options(page([nop]))] == [None]
