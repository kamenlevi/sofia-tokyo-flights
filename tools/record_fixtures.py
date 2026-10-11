"""Record small Google Flights fixtures for tests. Live: makes 3 requests."""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from selectolax.lexbor import LexborHTMLParser  # noqa: E402
from flightwatch.google.client import primp_transport  # noqa: E402
from flightwatch.google.parse import parse_options  # noqa: E402
from flightwatch.google.query import LegQuery, build_params  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def trim(html: str) -> str:
    node = LexborHTMLParser(html).css_first(r"script.ds\:1")
    return f"<html><head><title>Google Flights</title></head><body>{node.html}</body></html>"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    get = primp_transport()
    d = date.today() + timedelta(days=45)
    r = d + timedelta(days=15)
    p1 = build_params([LegQuery(d.isoformat(), "SOF", "TYO"), LegQuery(r.isoformat(), "TYO", "SOF")],
                      "economy", 4, 1, 1200, 1)
    s1, h1 = get(p1)
    (OUT / "stage1_rt.html").write_text(trim(h1))
    first = parse_options(h1)[0]
    time.sleep(2)
    p2 = build_params([LegQuery(d.isoformat(), "SOF", "TYO", first.selected()),
                       LegQuery(r.isoformat(), "TYO", "SOF")], "economy", 4, 1, 1200, 1)
    s2, h2 = get(p2)
    (OUT / "stage2_rt.html").write_text(trim(h2))
    time.sleep(2)
    p3 = build_params([LegQuery(d.isoformat(), "SOF", "IST")], "economy", 4, 0, None, 1)
    s3, h3 = get(p3)
    (OUT / "feeder_oneway.html").write_text(trim(h3))
    print("recorded", s1, s2, s3)


if __name__ == "__main__":
    main()
