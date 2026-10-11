import re
from pathlib import Path
from flightwatch.airlines import AirlineTable
from flightwatch.google.parse import parse_options

T = AirlineTable.load()


def test_every_entry_has_source_and_date():
    for a in T.airlines.values():
        assert a.source.startswith("https://") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.checked), a.code


def test_every_carrier_in_fixtures_is_covered():
    carriers = {s.carrier for f in (Path(__file__).parent / "fixtures").glob("*.html")
                for o in parse_options(f.read_text()) for s in o.leg.segments}
    assert carriers - set(T.airlines) == set()


def test_layout_match_by_aircraft_substring():
    lay = T.layout_for("LO", "Boeing 787", "economy")
    assert lay is not None and lay.layout.count("-") >= 1
