import json
from dataclasses import dataclass
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser

from flightwatch.google.query import SelectedSegment
from flightwatch.model import Leg, Segment


class GoogleFormatError(Exception):
    """Google's page did not have the layout we parse."""


class ConsentPageError(GoogleFormatError):
    """Google served its EU consent page instead of results."""


@dataclass(frozen=True)
class Option:
    leg: Leg
    total_eur: int | None      # whole party; None when Google lists no price
    seller: str                # airline code or "multi"

    def selected(self) -> tuple[SelectedSegment, ...]:
        return tuple(SelectedSegment(s.origin, f"{s.dep:%Y-%m-%d}", s.destination, s.carrier, s.number)
                     for s in self.leg.segments)


def _time(v) -> tuple[int, int]:
    padded = [*(v or []), None, None]
    return padded[0] or 0, padded[1] or 0


def _segment(x: list) -> Segment:
    dh, dm = _time(x[8])
    ah, am = _time(x[10])
    flight = x[22]
    airline = flight[3] if len(flight) > 3 and flight[3] else flight[0]
    return Segment(flight[0], str(flight[1]), airline, x[3], x[6],
                   datetime(*x[20], dh, dm), datetime(*x[21], ah, am), x[11], x[17] or "", x[14],
                   x[16] if len(x) > 16 and isinstance(x[16], int) else None)


def _payload(html: str):
    if "<title>Before you continue" in html:
        raise ConsentPageError("Google consent page; SOCS cookie missing or rejected")
    node = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if node is None:
        raise GoogleFormatError("no ds:1 script in page")
    js = node.text()
    if "data:" not in js:
        raise GoogleFormatError("ds:1 script has no data")
    data = js.split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise GoogleFormatError(f"ds:1 data is not JSON: {e}") from e


def parse_options(html: str) -> list[Option]:
    p = _payload(html)
    if p is None:
        return []
    best: dict[str, Option] = {}
    try:
        for sect in (3, 2):
            block = p[sect] if len(p) > sect else None
            if not block or not block[0]:
                continue
            for k in block[0]:
                f = k[0]
                try:
                    price = int(k[1][0][1])
                except (TypeError, IndexError, ValueError):
                    price = None
                leg = Leg(tuple(_segment(x) for x in f[2]), int(f[9]), tuple(int(l[0]) for l in (f[13] or [])))
                opt = Option(leg, price, f[0])
                old = best.get(leg.key)
                if old is None or (price is not None and (old.total_eur is None or price < old.total_eur)):
                    best[leg.key] = opt
    except (TypeError, IndexError, KeyError) as e:
        raise GoogleFormatError(f"unexpected itinerary layout: {e!r}") from e
    return list(best.values())
