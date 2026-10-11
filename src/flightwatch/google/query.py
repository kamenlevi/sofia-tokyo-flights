from base64 import b64encode
from dataclasses import dataclass
from urllib.parse import urlencode

from fast_flights import FlightQuery, Passengers, create_query


@dataclass(frozen=True)
class SelectedSegment:
    origin: str
    date: str          # YYYY-MM-DD, local departure date
    destination: str
    carrier: str
    number: str


@dataclass(frozen=True)
class LegQuery:
    date: str
    origin: str
    destination: str
    selected: tuple[SelectedSegment, ...] = ()


def _varint(n: int) -> bytes:
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def _field(num: int, payload: bytes) -> bytes:
    return _varint(num << 3 | 2) + _varint(len(payload)) + payload


def encode_selected(s: SelectedSegment) -> bytes:
    """FlightData field 4: a flight already chosen on this leg (found by the 2026-10-11 spike)."""
    inner = (_field(1, s.origin.encode()) + _field(2, s.date.encode()) + _field(3, s.destination.encode())
             + _field(5, s.carrier.encode()) + _field(6, s.number.encode()))
    return _field(4, inner)


def build_params(legs: list[LegQuery], cabin: str, adults: int, max_stops: int,
                 max_minutes: int | None, checked_bags: int) -> dict[str, str]:
    q = create_query(
        flights=[FlightQuery(date=l.date, from_airport=l.origin, to_airport=l.destination,
                             max_duration_minutes=max_minutes) for l in legs],
        seat=cabin, trip="round-trip" if len(legs) == 2 else "one-way",
        passengers=Passengers(adults=adults), language="en", currency="EUR",
        max_stops=max_stops, checked_bags=checked_bags)
    info = q.pb()
    for i, leg in enumerate(legs):
        if leg.selected:
            raw = info.data[i].SerializeToString() + b"".join(encode_selected(s) for s in leg.selected)
            info.data[i].ParseFromString(raw)   # protobuf keeps unknown field 4 on re-serialise
    return {"tfs": b64encode(info.SerializeToString()).decode(), "hl": "en", "curr": "EUR"}


def search_url(params: dict[str, str]) -> str:
    return "https://www.google.com/travel/flights/search?" + urlencode(params)


def booking_url(params: dict[str, str]) -> str:
    return "https://www.google.com/travel/flights/booking?" + urlencode(params)
