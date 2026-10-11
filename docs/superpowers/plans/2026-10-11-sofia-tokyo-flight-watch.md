# Sofia ↔ Tokyo Flight Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every day, a free GitHub Actions job searches Google Flights for every Sofia ↔ Tokyo return trip that matches the family's rules. It then emails kamenlevi@gmail.com the deals under budget, with a full HTML report attached.

**Architecture:**
- A Python package, `flightwatch`. It builds Google Flights search URLs itself: the protobuf `tfs` parameter, with selected-segment encoding for return pairings. It parses the embedded `ds:1` JSON payload into `Trip` objects, filters them with pure rule functions, and enriches them from static airline tables (meals, legroom, layouts, seat plans). It also scores them against the Bulgarian school calendar.
- The search runs as 16 parallel shard jobs. Shard results are encrypted with Fernet and uploaded as artifacts. A report job merges them, updates the encrypted price history, renders the report and sends the email.

**Tech Stack:**
- Python 3.12 or newer
- `fast-flights==3.1.0`: only for its protobuf messages and its `primp` HTTP client
- `selectolax` (comes with fast-flights)
- `cryptography` (Fernet)
- `pytest`
- GitHub Actions (public repo)
- Gmail SMTP
- macOS launchd (backup runner)

**Spec:** `docs/superpowers/specs/2026-10-11-sofia-tokyo-flight-watch-design.md`. Read it before starting.

## Global Constraints

- **Cost, a hard rule:** the daily run must never cost money or Claude usage.
  - No LLM or Claude calls at runtime.
  - No paid APIs.
  - No Duffel.
  - The repo is public, so standard GitHub runners are free.
  - At most 15,000 Google requests per run in total: 16 shards × 937.
- **No bot-check evasion.**
  - Use plain search-page GETs only.
  - The only cookie set is consent "reject all": `SOCS=CAI`.
  - Never call GetCalendarGraph or booking RPCs, and never try to produce BotGuard tokens.
  - At least 1.0 s between requests in each process.
- **Travellers:**
  - Party A is 4 people (3 adults and a 14-year-old).
  - Party B is 3 people (2 adults and a 14-year-old).
  - Search both as all adults. A 14-year-old pays the adult fare.
- **Budget per person** (whole return trip, one 23 kg bag and meals included):
  - economy: €1,200
  - premium economy: €1,300
- **Trip rules:**
  - Route: SOF to NRT or HND, and back.
  - Stay: Tokyo landing date to Tokyo departure date must be 10–21 days. Tag 14 days or more as recommended.
  - Departure window: from today + 14 days to today + 9 months, in Europe/Sofia dates.
  - Each direction: at most 2 flights and at most 1,200 minutes, waiting included.
- **Self-transfer (separate tickets):**
  - Connection at least 180 min at the same airport, or 300 min between the two airports of one city (IST/SAW, NRT/HND).
  - No overnight self-transfers.
  - Feeder flights are nonstop SOF ↔ hub. The long-haul is nonstop hub ↔ Tokyo.
- **Every result gets a booking link** on Google's booking page for that exact itinerary. Each ticket is labelled with the airline that sells it.
- **Results and history are stored encrypted:** Fernet, with key `FLIGHTWATCH_KEY`. Credentials live only in GitHub secrets or the macOS Keychain.
- **Days off:**
  - weekends;
  - Bulgarian public holidays;
  - the school holidays in the official 2026/27 Ministry of Education order;
  - all of 1–31 December 2026.
- **Interface text:** English, no emojis in code identifiers. Euro amounts are shown as `€1,084`.

## Review Focus

1. **Google sends a consent page, an HTTP error, or a changed page layout.** The run must report "search failed / X% checked", and must never send "no deals". *Tested in Task 4 and Task 13.*
2. **Overnight arrivals and shortened times.** Google writes `[None, 10]` for 00:10 and `[23]` for 23:00, and the arrival date can differ from the departure date. Arrival times and stay days must still come out right. *Tested in Task 3.*
3. **An itinerary listed without a price** (`k[1]` empty or null) must be skipped, not crash the shard. *Tested in Task 3.*
4. **The run date.** The cron fires at 03:00 UTC, which is 06:00 in Sofia, and must use Sofia's date. A window that crosses New Year must keep its first and last dates. *Tested in Task 5.*
5. **An airline or aircraft missing from the static tables** must show "not verified". The result must never be dropped. *Tested in Task 11.*

---

## File Structure

```
pyproject.toml
README.md                          # setup: secrets, Keychain, how to read the report
src/flightwatch/
  __init__.py
  config.py                        # Config dataclass + load_config()
  model.py                         # Segment, Leg, Ticket, Trip + (de)serialisation
  dates.py                         # Sofia "today", date-pair window, sharding, hub rotation
  calendar_bg.py                   # DaysOff: is_off(), school_days_missed()
  google/
    __init__.py
    query.py                       # LegQuery, SelectedSegment, build_params(), booking_url()
    parse.py                       # Option, parse_options(), GoogleFormatError, ConsentPageError
    client.py                      # GoogleClient: throttle, retries, request budget
  search.py                        # through-fare stage 1/2 + Party B
  selftransfer.py                  # hub return + feeder one-ways → separate-ticket trips
  rules.py                         # check(trip, cfg, addon_pp) -> list[str]
  seating.py                       # SeatPlan, plan_seats(layout, party)
  airlines.py                      # AirlineTable: lookup(), layout_for()
  enrich.py                        # Result, enrich()
  crypto.py                        # encrypt_json / decrypt_json
  shard.py                         # Coverage, ShardResult, run_shard(), merge_shards()
  history.py                       # load/save/record/trend
  report.py                        # render_html(), render_email()
  notify.py                        # send_email()
  cli.py                           # flightwatch shard|report|local|fallback-check
  data/
    __init__.py
    config.toml
    bg_calendar_2026_27.toml
    airlines.toml
tools/record_fixtures.py           # live: records small Google fixtures for tests
tests/
  googlefake.py                    # builds synthetic Google pages + FakeTransport
  fixtures/*.html                  # recorded, trimmed to the ds:1 script
  test_*.py
.github/workflows/daily.yml
mac/com.kamen.flightwatch.plist
mac/fallback.sh
```

---

### Task 1: Project skeleton, config and model

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/flightwatch/__init__.py`, `src/flightwatch/data/__init__.py`, `src/flightwatch/data/config.toml`, `src/flightwatch/config.py`, `src/flightwatch/model.py`
- Test: `tests/test_config.py`, `tests/test_model.py`

**Interfaces:**
- Produces: `load_config(path: Path | None = None) -> Config`. Fields are exactly those in `config.toml` below; `budget_pp_eur` is a dict keyed `"economy"` and `"premium-economy"`.
- Produces: `Segment`, `Leg`, `Ticket`, `Trip` (frozen dataclasses, fields below), plus `trip_to_dict(t) -> dict` and `trip_from_dict(d) -> Trip`.

- [ ] **Step 1: Create the skeleton files**

`pyproject.toml`:
```toml
[project]
name = "flightwatch"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fast-flights==3.1.0", "typing_extensions>=4.12", "cryptography>=43"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
flightwatch = "flightwatch.cli:main"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"flightwatch.data" = ["*.toml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["tests"]
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
report.html
shards/
*.bin.tmp
```

`src/flightwatch/__init__.py` and `src/flightwatch/data/__init__.py`: empty files.

`src/flightwatch/data/config.toml`:
```toml
origin = "SOF"
destination = "TYO"
tokyo_airports = ["NRT", "HND"]
timezone = "Europe/Sofia"
lead_days = 14
horizon_months = 9
stay_min = 10
stay_max = 21
stay_recommended = 14
max_leg_minutes = 1200
max_segments_per_leg = 2
parties = [4, 3]
checked_bags = 1
stage2_margin = 1.10
party_b_margin = 1.50
min_request_interval_s = 1.0
max_requests_per_run = 15000
shards = 16
hub_rotation_days = 7
hubs = ["IST", "DOH", "DXB", "FRA", "MUC", "WAW", "HEL"]
hubs_disabled = ["AUH", "VIE", "ZRH", "CDG", "AMS", "LHR", "FCO"]

[budget_pp_eur]
economy = 1200
"premium-economy" = 1300

[self_transfer]
same_airport_min = 180
city_change_min = 300
city_pairs = [["IST", "SAW"], ["NRT", "HND"]]
```

- [ ] **Step 2: Write failing tests**

`tests/test_config.py`:
```python
from flightwatch.config import load_config


def test_defaults_match_spec():
    cfg = load_config()
    assert cfg.origin == "SOF" and cfg.destination == "TYO"
    assert cfg.parties == (4, 3)
    assert cfg.budget_pp_eur == {"economy": 1200, "premium-economy": 1300}
    assert (cfg.stay_min, cfg.stay_max, cfg.stay_recommended) == (10, 21, 14)
    assert cfg.max_leg_minutes == 1200
    assert cfg.same_airport_min == 180 and cfg.city_change_min == 300
    assert frozenset({"IST", "SAW"}) in cfg.city_pairs
    assert cfg.max_requests_per_run // cfg.shards == 937
```

`tests/test_model.py`:
```python
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
```

- [ ] **Step 3: Run the tests and watch them fail**

Run:
```bash
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest -q
```
(Use `python3` if 3.12 is missing; any 3.12+ works.)

Expected: `ModuleNotFoundError: flightwatch.config`.

- [ ] **Step 4: Implement**

`src/flightwatch/config.py`:
```python
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Config:
    origin: str
    destination: str
    tokyo_airports: tuple[str, ...]
    timezone: str
    lead_days: int
    horizon_months: int
    stay_min: int
    stay_max: int
    stay_recommended: int
    max_leg_minutes: int
    max_segments_per_leg: int
    parties: tuple[int, ...]
    checked_bags: int
    stage2_margin: float
    party_b_margin: float
    min_request_interval_s: float
    max_requests_per_run: int
    shards: int
    hub_rotation_days: int
    hubs: tuple[str, ...]
    budget_pp_eur: dict[str, int]
    same_airport_min: int
    city_change_min: int
    city_pairs: tuple[frozenset[str], ...]


def load_config(path: Path | None = None) -> Config:
    text = path.read_text() if path else resources.files("flightwatch.data").joinpath("config.toml").read_text()
    raw = tomllib.loads(text)
    st = raw.pop("self_transfer")
    raw.pop("hubs_disabled", None)
    fields = {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items()}
    return Config(**fields,
                  same_airport_min=st["same_airport_min"],
                  city_change_min=st["city_change_min"],
                  city_pairs=tuple(frozenset(p) for p in st["city_pairs"]))
```

`src/flightwatch/model.py`:
```python
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass(frozen=True)
class Segment:
    carrier: str          # marketing airline code, e.g. "LO"
    number: str           # flight number without the code, e.g. "632"
    airline: str          # airline name as Google shows it
    origin: str
    destination: str
    dep: datetime         # local time at origin
    arr: datetime         # local time at destination
    minutes: int
    aircraft: str
    legroom: str | None   # Google's per-flight legroom, e.g. "31 in"

    @property
    def code(self) -> str:
        return f"{self.carrier}{self.number}"


@dataclass(frozen=True)
class Leg:
    segments: tuple[Segment, ...]
    minutes: int                  # first departure to last arrival, waiting included
    layovers: tuple[int, ...]     # minutes between consecutive segments

    @property
    def dep(self) -> datetime:
        return self.segments[0].dep

    @property
    def arr(self) -> datetime:
        return self.segments[-1].arr

    @property
    def origin(self) -> str:
        return self.segments[0].origin

    @property
    def destination(self) -> str:
        return self.segments[-1].destination

    @property
    def key(self) -> str:
        return "+".join(f"{s.code}@{s.dep:%Y-%m-%d}" for s in self.segments)


@dataclass(frozen=True)
class Ticket:
    seller: str                   # airline code the ticket is sold by, or "multi"
    segments: tuple[str, ...]     # segment codes this ticket covers
    total_eur: int                # whole party, bag included
    booking_url: str              # Google booking page for exactly this ticket


@dataclass(frozen=True)
class Trip:
    cabin: str                    # "economy" | "premium-economy"
    party: int
    outbound: Leg
    inbound: Leg
    tickets: tuple[Ticket, ...]

    @property
    def total_eur(self) -> int:
        return sum(t.total_eur for t in self.tickets)

    @property
    def per_person_eur(self) -> float:
        return self.total_eur / self.party

    @property
    def stay_days(self) -> int:
        return (self.inbound.dep.date() - self.outbound.arr.date()).days

    @property
    def self_transfer(self) -> bool:
        return len(self.tickets) > 1

    @property
    def key(self) -> str:
        return f"{self.cabin}|{self.party}|{self.outbound.key}|{self.inbound.key}"


def trip_to_dict(t: Trip) -> dict:
    def conv(o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, dict):
            return {k: conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(v) for v in o]
        return o
    return conv(asdict(t))


def _seg(d: dict) -> Segment:
    return Segment(**{**d, "dep": datetime.fromisoformat(d["dep"]), "arr": datetime.fromisoformat(d["arr"])})


def _leg(d: dict) -> Leg:
    return Leg(tuple(_seg(s) for s in d["segments"]), d["minutes"], tuple(d["layovers"]))


def trip_from_dict(d: dict) -> Trip:
    return Trip(d["cabin"], d["party"], _leg(d["outbound"]), _leg(d["inbound"]),
                tuple(Ticket(t["seller"], tuple(t["segments"]), t["total_eur"], t["booking_url"])
                      for t in d["tickets"]))
```

- [ ] **Step 5: Run the tests and check they pass**

Run: `.venv/bin/pytest -q`. Expected: 3 passed.

- [ ] **Step 6: Commit**
```bash
git add -A && git commit -m "Add project skeleton, config and trip model"
```

---

### Task 2: Google query builder

**Files:**
- Create: `src/flightwatch/google/__init__.py` (empty), `src/flightwatch/google/query.py`
- Test: `tests/test_query.py`

**Interfaces:**
- Produces:
  - `SelectedSegment(origin, date, destination, carrier, number)`
  - `LegQuery(date: str, origin: str, destination: str, selected: tuple[SelectedSegment, ...] = ())`
  - `encode_selected(s) -> bytes`
  - `build_params(legs: list[LegQuery], cabin: str, adults: int, max_stops: int, max_minutes: int | None, checked_bags: int) -> dict[str, str]`, which returns the keys `tfs`, `hl`, `curr`
  - `booking_url(params) -> str`
  - `search_url(params) -> str`

- [ ] **Step 1: Write failing tests**

`tests/test_query.py`:
```python
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
```

- [ ] **Step 2: Run them and watch them fail**

Run: `.venv/bin/pytest tests/test_query.py -q`. Expected: ImportError.

- [ ] **Step 3: Implement** `src/flightwatch/google/query.py`
```python
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
```

- [ ] **Step 4: Run the tests and check they pass.** Expected: 4 passed. If `test_selected_segments_survive_serialisation` fails, the installed protobuf runtime drops unknown fields. In that case append the raw bytes to the serialised `Info` instead: rebuild `Info` by hand from its fields, splicing in the extended `FlightData` bytes as field 3. Then rerun.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Build Google Flights queries, including selected-segment pairing"
```

---

### Task 3: Google page parser, with fixtures

**Files:**
- Create: `src/flightwatch/google/parse.py`, `tests/googlefake.py`, `tools/record_fixtures.py`, `tests/fixtures/` (recorded)
- Test: `tests/test_parse.py`

**Interfaces:**
- Consumes: `Segment`, `Leg` (Task 1), `SelectedSegment` (Task 2)
- Produces:
  - `Option(leg: Leg, total_eur: int | None, seller: str)`, with method `selected() -> tuple[SelectedSegment, ...]`
  - `parse_options(html: str) -> list[Option]`
  - exceptions `GoogleFormatError` and `ConsentPageError(GoogleFormatError)`
  - in `tests/googlefake.py`: `seg(...)`, `itin(...)`, `page(best, other)`, `FakeTransport`

Payload layout, confirmed live on 2026-10-11:
- `payload[3][0]` holds the "best" itineraries and `payload[2][0]` the "other" ones. Each item `k` holds the itinerary in `k[0]` and the total price for all passengers in `k[1][0][1]`.
- Itinerary `f`:
  - `f[0]`: seller code, or `"multi"`
  - `f[2]`: segments
  - `f[9]`: leg minutes
  - `f[13]`: list of `[layover_minutes, ...]`
- Segment `x`:
  - `x[3]` and `x[6]`: origin and destination
  - `x[8]` and `x[10]`: departure and arrival `[h, m]`, with zeros dropped
  - `x[11]`: minutes
  - `x[14]`: legroom ("31 in")
  - `x[17]`: aircraft
  - `x[20]` and `x[21]`: departure and arrival `[y, m, d]`
  - `x[22]`: `[carrier, number, None, airline name]`

- [ ] **Step 1: Write the synthetic page helper** `tests/googlefake.py`
```python
import json


def seg(o, d, dep_date, dep_t, arr_date, arr_t, mins, carrier, num, aircraft="Boeing 787", legroom="31 in"):
    x = [None] * 23
    x[3], x[6], x[8], x[10], x[11] = o, d, dep_t, arr_t, mins
    x[14], x[17], x[20], x[21] = legroom, aircraft, dep_date, arr_date
    x[22] = [carrier, num, None, f"Airline {carrier}"]
    return x


def itin(seller, segs, leg_minutes, layovers, price):
    f = [None] * 23
    f[0], f[1], f[2], f[9] = seller, [f"Airline {seller}"], segs, leg_minutes
    f[13] = [[m, "X", "X"] for m in layovers] or None
    return [f, None if price is None else [[None, price], "token"]]


def page(best, other=()):
    p = [None] * 32
    p[3] = [list(best) or None]
    p[2] = [list(other)] if other else None
    data = json.dumps(p)
    return ("<html><head><title>Google Flights</title></head><body>"
            f"<script class=\"ds:1\" nonce=\"x\">AF_initDataCallback({{key: 'ds:1', hash: '1', data:{data}, sideChannel: {{}}}});</script>"
            "</body></html>")


CONSENT = "<html><head><title>Before you continue</title></head><body>consent</body></html>"


class FakeTransport:
    """Returns queued (status, html) responses and records the params of every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, params):
        self.calls.append(params)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
```

- [ ] **Step 2: Write failing tests** `tests/test_parse.py`
```python
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
```

- [ ] **Step 3: Write the fixture recorder** `tools/record_fixtures.py`. It makes 3 live requests, 2 s apart, and keeps only the `ds:1` script.
```python
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
```

- [ ] **Step 4: Run the tests and watch them fail.** Run `.venv/bin/pytest tests/test_parse.py -q`. Expected: ImportError.

- [ ] **Step 5: Implement** `src/flightwatch/google/parse.py`
```python
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
                   datetime(*x[20], dh, dm), datetime(*x[21], ah, am), x[11], x[17] or "", x[14])


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
```

- [ ] **Step 6: Implement `primp_transport`** before recording. Task 4 adds the client class around it; for now create `src/flightwatch/google/client.py` with only this:
```python
URL = "https://www.google.com/travel/flights"


def primp_transport():
    from primp import Client
    c = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
    c.set_cookies("https://www.google.com", {"SOCS": "CAI"})   # consent: reject all

    def get(params: dict[str, str]) -> tuple[int, str]:
        r = c.get(URL, params=params)
        return r.status_code, r.text
    return get
```

- [ ] **Step 7: Record the fixtures (live, 3 requests).** Run `.venv/bin/python tools/record_fixtures.py`. Expected: `recorded 200 200 200` and three files under `tests/fixtures/` of a few hundred KB.

- [ ] **Step 8: Run the tests and check they pass.** Expected: 11 passed.

- [ ] **Step 9: Commit**
```bash
git add -A && git commit -m "Parse Google Flights result pages into options"
```

---

### Task 4: Google client: throttling, retries and request budget

**Files:**
- Modify: `src/flightwatch/google/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `parse_options`, `ConsentPageError`, `GoogleFormatError` (Task 3)
- Produces:
  - `GoogleClient(transport=None, min_interval=1.0, max_requests=937, retries=3, sleep=time.sleep, clock=time.monotonic)`
  - `.search(params) -> list[Option]`
  - counters `.requests` and `.failures`
  - exceptions `SearchFailed(Exception)` and `BudgetExceeded(Exception)`

- [ ] **Step 1: Write failing tests** `tests/test_client.py`
```python
import pytest
from googlefake import FakeTransport, page, itin, seg, CONSENT
from flightwatch.google.client import GoogleClient, SearchFailed, BudgetExceeded
from flightwatch.google.parse import ConsentPageError

OK = (200, page([itin("TK", [seg("SOF", "IST", [2027, 3, 5], [9, 30], [2027, 3, 5], [12], 90, "TK", "1")], 90, [], 500)]))


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def now(self):
        return self.t


def client(responses, **kw):
    c = Clock()
    t = FakeTransport(responses)
    return GoogleClient(transport=t, sleep=c.sleep, clock=c.now, **kw), t, c


def test_throttles_between_requests():
    g, t, c = client([OK, OK], min_interval=1.0)
    g.search({"tfs": "a"})
    g.search({"tfs": "b"})
    assert c.sleeps == [1.0]
    assert g.requests == 2


def test_retries_then_succeeds():
    g, t, c = client([(503, ""), OK], min_interval=0)
    assert len(g.search({})) == 1
    assert g.requests == 2 and g.failures == 0


def test_gives_up_after_retries_and_counts_failure():
    g, t, c = client([(500, "")] * 3, min_interval=0)
    with pytest.raises(SearchFailed):
        g.search({})
    assert g.failures == 1


def test_consent_page_is_not_retried():
    g, t, c = client([(200, CONSENT)], min_interval=0)
    with pytest.raises(ConsentPageError):
        g.search({})
    assert g.requests == 1


def test_layout_change_counts_as_failure_not_empty():
    g, t, c = client([(200, "<html>new layout</html>")] * 3, min_interval=0)
    with pytest.raises(SearchFailed):
        g.search({})


def test_request_budget():
    g, t, c = client([OK], min_interval=0, max_requests=1)
    g.search({})
    with pytest.raises(BudgetExceeded):
        g.search({})
```

- [ ] **Step 2: Run them and watch them fail.** Expected: ImportError.

- [ ] **Step 3: Implement.** Replace `src/flightwatch/google/client.py` with:
```python
import time
from collections.abc import Callable

from flightwatch.google.parse import ConsentPageError, GoogleFormatError, Option, parse_options

URL = "https://www.google.com/travel/flights"
Transport = Callable[[dict[str, str]], tuple[int, str]]


class SearchFailed(Exception):
    """A search kept failing after retries."""


class BudgetExceeded(Exception):
    """This process reached its request budget."""


def primp_transport() -> Transport:
    from primp import Client
    c = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
    c.set_cookies("https://www.google.com", {"SOCS": "CAI"})   # consent: reject all

    def get(params: dict[str, str]) -> tuple[int, str]:
        r = c.get(URL, params=params)
        return r.status_code, r.text
    return get


class GoogleClient:
    def __init__(self, transport: Transport | None = None, min_interval: float = 1.0, max_requests: int = 937,
                 retries: int = 3, sleep=time.sleep, clock=time.monotonic):
        self.transport = transport or primp_transport()
        self.min_interval = min_interval
        self.max_requests = max_requests
        self.retries = retries
        self.sleep = sleep
        self.clock = clock
        self.requests = 0
        self.failures = 0
        self._last: float | None = None

    def _throttle(self) -> None:
        if self._last is not None:
            wait = self._last + self.min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def search(self, params: dict[str, str]) -> list[Option]:
        last = "no attempt"
        for attempt in range(self.retries):
            if self.requests >= self.max_requests:
                raise BudgetExceeded(f"{self.requests} requests made")
            self._throttle()
            self.requests += 1
            try:
                status, text = self.transport(params)
                if status == 200:
                    return parse_options(text)
                last = f"HTTP {status}"
                backoff = 60 * (attempt + 1) if status == 429 else 5 * 2 ** attempt
            except ConsentPageError:
                raise
            except GoogleFormatError as e:
                last, backoff = str(e), 5 * 2 ** attempt
            except Exception as e:  # network errors
                last, backoff = f"{type(e).__name__}: {e}", 5 * 2 ** attempt
            if attempt < self.retries - 1:
                self.sleep(backoff)
        self.failures += 1
        raise SearchFailed(last)
```

- [ ] **Step 4: Run the tests and check they pass.** Run `.venv/bin/pytest -q`. Expected: all pass. `test_throttles_between_requests` expects only the 1.0 s throttle sleep, with no backoff.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Throttle, retry and budget Google requests"
```

---

### Task 5: Date window, sharding and hub rotation

**Files:**
- Create: `src/flightwatch/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: `Config`
- Produces:
  - `today_in(tz, now=None) -> date`
  - `add_months(d, n) -> date`
  - `date_pairs(today, cfg, limit_days: int | None = None) -> list[tuple[date, date]]`; `limit_days` keeps only the first N departure dates, for smoke runs
  - `shard(items, total, index) -> list`
  - `hub_pairs_today(pairs, today, days) -> list[tuple[date, date]]`

- [ ] **Step 1: Write failing tests** `tests/test_dates.py`
```python
from datetime import date, datetime, timezone
from flightwatch.config import load_config
from flightwatch.dates import today_in, add_months, date_pairs, shard, hub_pairs_today

CFG = load_config()


def test_sofia_date_at_cron_time():
    # 22:30 UTC on 31 Dec is already 1 Jan in Sofia
    assert today_in("Europe/Sofia", datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc)) == date(2027, 1, 1)


def test_add_months_clamps_day():
    assert add_months(date(2026, 5, 31), 9) == date(2027, 2, 28)


def test_window_bounds_and_gaps_across_new_year():
    pairs = date_pairs(date(2026, 12, 20), CFG)
    outs = sorted({d for d, _ in pairs})
    assert outs[0] == date(2027, 1, 3)              # +14 days
    assert outs[-1] == date(2027, 9, 20)            # +9 months
    gaps = sorted({(r - d).days for d, r in pairs})
    assert gaps == list(range(10, 23))              # landing may be the next day
    assert len(pairs) == len(outs) * 13


def test_limit_days_for_smoke_runs():
    assert len(date_pairs(date(2026, 10, 11), CFG, limit_days=1)) == 13


def test_shards_partition_everything():
    pairs = date_pairs(date(2026, 10, 11), CFG)
    parts = [shard(pairs, 16, i) for i in range(16)]
    assert sum(len(p) for p in parts) == len(pairs)
    assert set().union(*map(set, parts)) == set(pairs)


def test_hub_rotation_covers_each_pair_once_per_week():
    days = [date(2026, 11, 1 + i) for i in range(7)]
    pair = (date(2027, 2, 10), date(2027, 2, 24))
    hits = [day for day in days if pair in hub_pairs_today([pair], day, 7)]
    assert len(hits) == 1
```

- [ ] **Step 2: Run them and watch them fail.** Expected: ImportError.

- [ ] **Step 3: Implement** `src/flightwatch/dates.py`
```python
import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def today_in(tz: str, now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(tz)).date()


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def date_pairs(today: date, cfg, limit_days: int | None = None) -> list[tuple[date, date]]:
    """Every (leave Sofia, leave Tokyo) date pair to search. Landing in Tokyo can be the next day,
    so the gap runs from stay_min to stay_max + 1."""
    first, last = today + timedelta(days=cfg.lead_days), add_months(today, cfg.horizon_months)
    if limit_days is not None:
        last = min(last, first + timedelta(days=limit_days - 1))
    pairs, d = [], first
    while d <= last:
        pairs += [(d, d + timedelta(days=g)) for g in range(cfg.stay_min, cfg.stay_max + 2)]
        d += timedelta(days=1)
    return pairs


def shard(items: list, total: int, index: int) -> list:
    return items[index::total]


def hub_pairs_today(pairs: list[tuple[date, date]], today: date, days: int) -> list[tuple[date, date]]:
    """Stable rotation: each pair is searched on exactly one day in every `days`-day cycle."""
    return [(d, r) for d, r in pairs if (d.toordinal() * 31 + (r - d).days) % days == today.toordinal() % days]
```

- [ ] **Step 4: Run the tests and check they pass.** Expected: 6 passed.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Generate the date window, shards and hub rotation"
```

---

### Task 6: Bulgarian school and holiday calendar

**Files:**
- Create: `src/flightwatch/data/bg_calendar_2026_27.toml`, `src/flightwatch/calendar_bg.py`
- Test: `tests/test_calendar.py`

**Interfaces:**
- Produces:
  - `DaysOff.load(path=None) -> DaysOff`
  - `.is_off(d) -> bool`
  - `.school_days_missed(first: date, last: date) -> int` (inclusive range)
  - `.source -> str`

- [ ] **Step 1: Research the official dates.**
  - Find the Ministry of Education order on the 2026/27 school year: search mon.bg for "заповед график учебно време 2026/2027". Collect:
    - the autumn, Christmas, mid-year, spring and Easter breaks;
    - the last school day for grades 7 and 8 (the child is 14);
    - any extra days off the order names.
  - Find Bulgaria's official public holidays from October 2026 to July 2027, from the Council of Ministers or the Labour Code list, including any moved days off. The fixed ones are 1 Jan, 3 Mar, 1 May, 6 May, 24 May, 6 Sep, 22 Sep and 24–26 Dec. Orthodox Easter 2027 is 2 May: confirm it, then add Good Friday 30 Apr through Easter Monday 3 May.
  - If the 2026/27 order is not published yet, stop and tell Kamen. Do not guess school dates.

- [ ] **Step 2: Write the data file** `src/flightwatch/data/bg_calendar_2026_27.toml`. Fill it in this format with the researched dates; every range is inclusive:
```toml
source = "<URL of the Ministry order>"
holidays_source = "<URL of the public-holiday list>"
retrieved = "<YYYY-MM-DD>"
school_year_end = "<last school day for grade 7/8, e.g. 2027-06-30>"   # every later day is off
off = [
  ["2026-12-01", "2026-12-31"],   # Kamen: all of December counts as off
  # school breaks from the order, e.g. ["2026-10-31", "2026-11-03"],
  # public holidays and moved days off, e.g. ["2027-03-03", "2027-03-03"],
]
```

- [ ] **Step 3: Write failing tests** `tests/test_calendar.py`. The first two tests hold no matter what the order says. The third pins a few dates against the order, so check them after Step 1.
```python
from datetime import date, timedelta
from flightwatch.calendar_bg import DaysOff

CAL = DaysOff.load()


def test_weekends_and_all_of_december_are_off():
    assert CAL.is_off(date(2027, 2, 13))          # Saturday
    assert all(CAL.is_off(date(2026, 12, d)) for d in range(1, 32))


def test_after_school_year_everything_is_off():
    assert CAL.is_off(date(2027, 7, 15))


def test_known_dates():
    assert CAL.is_off(date(2027, 3, 3))           # Liberation Day (a Wednesday)
    assert CAL.is_off(date(2027, 5, 6))           # St George's Day (a Thursday)
    assert not CAL.is_off(date(2026, 11, 11))     # an ordinary Wednesday; confirm against the order


def test_school_days_missed_counts_inclusive_weekdays_not_off():
    # Both ends count: leaving on a school day or landing home on one still misses it
    first, last = date(2027, 3, 5), date(2027, 3, 20)
    expected = sum(1 for i in range(16) if not CAL.is_off(first + timedelta(days=i)))
    assert CAL.school_days_missed(first, last) == expected
    assert CAL.school_days_missed(date(2027, 3, 5), date(2027, 3, 5)) == (0 if CAL.is_off(date(2027, 3, 5)) else 1)
    assert CAL.school_days_missed(date(2026, 12, 5), date(2026, 12, 22)) == 0
```

- [ ] **Step 4: Run them and watch them fail.** Expected: ImportError.

- [ ] **Step 5: Implement** `src/flightwatch/calendar_bg.py`
```python
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class DaysOff:
    ranges: tuple[tuple[date, date], ...]
    school_year_end: date
    source: str

    @classmethod
    def load(cls, path: Path | None = None) -> "DaysOff":
        text = (path.read_text() if path else
                resources.files("flightwatch.data").joinpath("bg_calendar_2026_27.toml").read_text())
        raw = tomllib.loads(text)
        return cls(tuple((date.fromisoformat(a), date.fromisoformat(b)) for a, b in raw["off"]),
                   date.fromisoformat(raw["school_year_end"]), raw["source"])

    def is_off(self, d: date) -> bool:
        return d.weekday() >= 5 or d > self.school_year_end or any(a <= d <= b for a, b in self.ranges)

    def school_days_missed(self, first: date, last: date) -> int:
        return sum(1 for i in range((last - first).days + 1) if not self.is_off(first + timedelta(days=i)))
```

- [ ] **Step 6: Run the tests and check they pass.**

- [ ] **Step 7: Commit**
```bash
git add -A && git commit -m "Add the Bulgarian 2026/27 school calendar"
```

---

### Task 7: Rules engine

**Files:**
- Create: `src/flightwatch/rules.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Consumes: `Trip`, `Config`
- Produces:
  - `check(trip, cfg, addon_pp: float = 0.0) -> list[str]`: human-readable problems; an empty list means the trip qualifies
  - `price_pp(trip, addon_pp) -> float`
  - `structural_problems(trip, cfg) -> list[str]`: every rule except budget

- [ ] **Step 1: Write failing tests** `tests/test_rules.py`
```python
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
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/rules.py`
```python
from flightwatch.model import Leg, Trip


def _hm(minutes: int) -> str:
    return f"{minutes // 60}h{minutes % 60:02d}"


def _leg_problems(name: str, leg: Leg, cfg) -> list[str]:
    p = []
    if len(leg.segments) > cfg.max_segments_per_leg:
        p.append(f"{name}: {len(leg.segments)} flights (max {cfg.max_segments_per_leg})")
    if leg.minutes > cfg.max_leg_minutes:
        p.append(f"{name}: {_hm(leg.minutes)} door to door (max 20h)")
    return p


def _self_transfer_problems(name: str, leg: Leg, cfg) -> list[str]:
    p = []
    for i, lay in enumerate(leg.layovers):
        a, b = leg.segments[i].destination, leg.segments[i + 1].origin
        if a == b:
            need = cfg.same_airport_min
        elif frozenset({a, b}) in cfg.city_pairs:
            need = cfg.city_change_min
        else:
            p.append(f"{name}: self-transfer needs an airport change {a}→{b}")
            continue
        if lay < need:
            p.append(f"{name}: self-transfer at {a} is {_hm(lay)}, needs {_hm(need)} for bags, check-in and security")
    return p


def structural_problems(trip: Trip, cfg) -> list[str]:
    p = _leg_problems("outbound", trip.outbound, cfg) + _leg_problems("return", trip.inbound, cfg)
    if trip.outbound.destination not in cfg.tokyo_airports or trip.inbound.origin not in cfg.tokyo_airports:
        p.append("does not land in / leave from Tokyo (NRT/HND)")
    if not cfg.stay_min <= trip.stay_days <= cfg.stay_max:
        p.append(f"stay of {trip.stay_days} days (allowed {cfg.stay_min}–{cfg.stay_max})")
    if trip.self_transfer:
        p += _self_transfer_problems("outbound", trip.outbound, cfg) + _self_transfer_problems("return", trip.inbound, cfg)
    return p


def price_pp(trip: Trip, addon_pp: float = 0.0) -> float:
    return trip.per_person_eur + addon_pp


def check(trip: Trip, cfg, addon_pp: float = 0.0) -> list[str]:
    p = structural_problems(trip, cfg)
    budget = cfg.budget_pp_eur[trip.cabin]
    if price_pp(trip, addon_pp) > budget:
        p.append(f"€{price_pp(trip, addon_pp):,.0f} per person is over the €{budget:,} budget")
    return p
```

- [ ] **Step 4: Run the tests and check they pass.**

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Add trip rules: flights, 20h limit, stay, self-transfer, budget"
```

---

### Task 8: Through-fare search (stage 1 and 2, Party B)

**Files:**
- Create: `src/flightwatch/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `GoogleClient.search`, `build_params`, `booking_url`, `LegQuery`, `Option`, `Trip`, `Ticket`
- Produces:
  - `PairResult(min_pp: float | None, trips: list[Trip], requests: int)`
  - `search_pair(client, cfg, d: date, r: date, cabin: str, adults: int) -> PairResult`
  - `search_pair_all_parties(client, cfg, d, r, cabin) -> list[Trip]`

- [ ] **Step 1: Write failing tests** `tests/test_search.py`
```python
from datetime import date
from googlefake import FakeTransport, page, itin, seg
from flightwatch.config import load_config
from flightwatch.google.client import GoogleClient
from flightwatch.search import search_pair, search_pair_all_parties

CFG = load_config()
D, R = date(2027, 3, 5), date(2027, 3, 20)


def out_opt(price, num="50"):
    return itin("TK", [seg("SOF", "IST", [2027, 3, 5], [9, 30], [2027, 3, 5], [12], 90, "TK", "1028"),
                       seg("IST", "NRT", [2027, 3, 5], [15, 25], [2027, 3, 6], [8, 40], 675, "TK", num)], 970, [205], price)


def ret_opt(price):
    return itin("TK", [seg("NRT", "IST", [2027, 3, 20], [10], [2027, 3, 20], [17], 780, "TK", "51"),
                       seg("IST", "SOF", [2027, 3, 20], [19], [2027, 3, 20], [20, 30], 90, "TK", "1027")], 1050, [120], price)


def make(responses):
    t = FakeTransport([(200, r) for r in responses])
    return GoogleClient(transport=t, min_interval=0), t


def test_cheap_outbound_gets_stage2_and_every_return_becomes_a_trip():
    g, t = make([page([out_opt(4400), out_opt(9000, "52")]), page([ret_opt(4400), ret_opt(4700)])])
    res = search_pair(g, CFG, D, R, "economy", 4)
    assert res.min_pp == 1100
    assert len(t.calls) == 2                       # the €9,000 outbound is skipped: over budget × 1.10
    assert sorted(x.total_eur for x in res.trips) == [4400, 4700]
    assert res.trips[0].tickets[0].booking_url.startswith("https://www.google.com/travel/flights/booking?tfs=")


def test_nothing_near_budget_means_one_request():
    g, t = make([page([out_opt(8000)])])
    res = search_pair(g, CFG, D, R, "economy", 4)
    assert res.trips == [] and res.min_pp == 2000 and len(t.calls) == 1


def test_party_b_searched_only_when_party_a_within_1_5x():
    g, t = make([page([out_opt(6800)]),            # A: €1,700 pp is within 1.5 × €1,200, so search B
                 page([out_opt(3300)]), page([ret_opt(3300)])])   # B: €1,100 pp
    trips = search_pair_all_parties(g, CFG, D, R, "economy")
    assert [x.party for x in trips] == [3]
    g2, t2 = make([page([out_opt(9000)])])          # A: €2,250 pp, so B is not searched
    assert search_pair_all_parties(g2, CFG, D, R, "economy") == [] and len(t2.calls) == 1
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/search.py`
```python
from dataclasses import dataclass, field
from datetime import date

from flightwatch.google.query import LegQuery, booking_url, build_params
from flightwatch.model import Ticket, Trip


@dataclass
class PairResult:
    min_pp: float | None
    trips: list[Trip] = field(default_factory=list)


def _legs(cfg, d: date, r: date, selected=()):
    return [LegQuery(d.isoformat(), cfg.origin, cfg.destination, selected),
            LegQuery(r.isoformat(), cfg.destination, cfg.origin)]


def search_pair(client, cfg, d: date, r: date, cabin: str, adults: int) -> PairResult:
    budget = cfg.budget_pp_eur[cabin]
    stage1 = client.search(build_params(_legs(cfg, d, r), cabin, adults, 1, cfg.max_leg_minutes, cfg.checked_bags))
    outs = [o for o in stage1 if o.total_eur is not None]
    if not outs:
        return PairResult(None)
    res = PairResult(min(o.total_eur for o in outs) / adults)
    for o in outs:
        if o.total_eur / adults > budget * cfg.stage2_margin:
            continue
        params = build_params(_legs(cfg, d, r, o.selected()), cabin, adults, 1, cfg.max_leg_minutes, cfg.checked_bags)
        for ret in client.search(params):
            if ret.total_eur is None:
                continue
            seller = o.seller if o.seller == ret.seller else "multi"
            both = build_params([LegQuery(d.isoformat(), cfg.origin, cfg.destination, o.selected()),
                                 LegQuery(r.isoformat(), cfg.destination, cfg.origin, ret.selected())],
                                cabin, adults, 1, cfg.max_leg_minutes, cfg.checked_bags)
            codes = tuple(s.code for s in o.leg.segments + ret.leg.segments)
            res.trips.append(Trip(cabin, adults, o.leg, ret.leg,
                                  (Ticket(seller, codes, ret.total_eur, booking_url(both)),)))
    return res


def search_pair_all_parties(client, cfg, d: date, r: date, cabin: str) -> list[Trip]:
    big, small = cfg.parties
    a = search_pair(client, cfg, d, r, cabin, big)
    trips = list(a.trips)
    if a.min_pp is not None and a.min_pp <= cfg.budget_pp_eur[cabin] * cfg.party_b_margin:
        trips += search_pair(client, cfg, d, r, cabin, small).trips
    return trips
```

- [ ] **Step 4: Run the tests and check they pass.** In the Party B test, Party A's stage 1 at €1,700 per person makes no stage-2 call, because €1,700 > €1,320. Then B makes its stage-1 and stage-2 calls, for 3 calls in total.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Search every outbound/return pairing for each date pair"
```

---

### Task 9: Separate tickets through hubs

**Files:**
- Create: `src/flightwatch/selftransfer.py`
- Test: `tests/test_selftransfer.py`

**Interfaces:**
- Consumes: `GoogleClient.search`, `build_params`, `booking_url`, `LegQuery`, `Option`, `Leg`, `Ticket`, `Trip`, `rules._self_transfer_problems` is **not** used. The trips are only built here; the rules engine judges them later.
- Produces:
  - `join(first: Leg, second: Leg) -> Leg`
  - `FeederCache` (a dict alias)
  - `search_hub_pair(client, cfg, hub, d, r, cabin, adults, cache) -> list[Trip]`

- [ ] **Step 1: Write failing tests** `tests/test_selftransfer.py`
```python
from datetime import date
from googlefake import FakeTransport, page, itin, seg
from flightwatch.config import load_config
from flightwatch.google.client import GoogleClient
from flightwatch.selftransfer import search_hub_pair, join
from flightwatch.google.parse import parse_options

CFG = load_config()

LH_OUT = itin("TK", [seg("IST", "NRT", [2027, 3, 5], [15, 25], [2027, 3, 6], [8, 40], 675, "TK", "50")], 675, [], 3000)
LH_RET = itin("TK", [seg("NRT", "IST", [2027, 3, 20], [10], [2027, 3, 20], [17], 780, "TK", "51")], 780, [], 3000)
FEED_OUT = itin("FB", [seg("SOF", "IST", [2027, 3, 5], [9], [2027, 3, 5], [11], 60, "FB", "471")], 60, [], 400)
FEED_RET = itin("FB", [seg("IST", "SOF", [2027, 3, 20], [20, 30], [2027, 3, 20], [21, 30], 60, "FB", "472")], 60, [], 400)


def test_join_computes_layover_and_total():
    a = parse_options(page([FEED_OUT]))[0].leg
    b = parse_options(page([LH_OUT]))[0].leg
    j = join(a, b)
    assert j.layovers == (265,)                    # 11:00 to 15:25
    assert j.minutes == 60 + 265 + 675


def test_hub_pair_builds_three_ticket_trip_and_fetches_feeders_lazily():
    t = FakeTransport([(200, page([LH_OUT])), (200, page([LH_RET])), (200, page([FEED_OUT])), (200, page([FEED_RET]))])
    g = GoogleClient(transport=t, min_interval=0)
    trips = search_hub_pair(g, CFG, "IST", date(2027, 3, 5), date(2027, 3, 20), "economy", 4, {})
    [trip] = trips
    assert [tk.seller for tk in trip.tickets] == ["FB", "TK", "FB"]
    assert trip.total_eur == 3800 and trip.self_transfer
    assert [s.code for s in trip.outbound.segments] == ["FB471", "TK50"]


def test_expensive_long_haul_skips_feeders():
    pricey = itin("TK", LH_OUT[0][2], 675, [], 6000)
    t = FakeTransport([(200, page([pricey]))])
    g = GoogleClient(transport=t, min_interval=0)
    assert search_hub_pair(g, CFG, "IST", date(2027, 3, 5), date(2027, 3, 20), "economy", 4, {}) == []
    assert len(t.calls) == 1
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/selftransfer.py`
```python
from datetime import date

from flightwatch.google.query import LegQuery, booking_url, build_params
from flightwatch.model import Leg, Ticket, Trip

FeederCache = dict


def join(first: Leg, second: Leg) -> Leg:
    lay = int((second.dep - first.arr).total_seconds() // 60)
    return Leg(first.segments + second.segments, first.minutes + lay + second.minutes, first.layovers + (lay,) + second.layovers)


def _feeders(client, cfg, origin: str, dest: str, day: date, adults: int, cache: FeederCache):
    key = (origin, dest, day, adults)
    if key not in cache:
        params = build_params([LegQuery(day.isoformat(), origin, dest)], "economy", adults, 0, None, cfg.checked_bags)
        cache[key] = [(o, booking_url(build_params([LegQuery(day.isoformat(), origin, dest, o.selected())],
                                                   "economy", adults, 0, None, cfg.checked_bags)))
                      for o in client.search(params) if o.total_eur is not None]
    return cache[key]


def search_hub_pair(client, cfg, hub: str, d: date, r: date, cabin: str, adults: int, cache: FeederCache) -> list[Trip]:
    budget = cfg.budget_pp_eur[cabin]

    def legs(sel_out=(), sel_ret=()):
        return [LegQuery(d.isoformat(), hub, cfg.destination, sel_out), LegQuery(r.isoformat(), cfg.destination, hub, sel_ret)]

    outs = [o for o in client.search(build_params(legs(), cabin, adults, 0, None, cfg.checked_bags))
            if o.total_eur is not None and o.total_eur / adults <= budget]
    trips = []
    for o in outs:
        rets = [x for x in client.search(build_params(legs(o.selected()), cabin, adults, 0, None, cfg.checked_bags))
                if x.total_eur is not None and x.total_eur / adults <= budget]
        if not rets:
            continue
        feed_out = [(f, u) for f, u in _feeders(client, cfg, cfg.origin, hub, o.leg.dep.date(), adults, cache)
                    if f.leg.arr < o.leg.dep]
        for ret in rets:
            lh_url = booking_url(build_params(legs(o.selected(), ret.selected()), cabin, adults, 0, None, cfg.checked_bags))
            lh = Ticket(o.seller, tuple(s.code for s in o.leg.segments + ret.leg.segments), ret.total_eur, lh_url)
            feed_back = [(f, u) for f, u in _feeders(client, cfg, hub, cfg.origin, ret.leg.arr.date(), adults, cache)
                         if f.leg.dep > ret.leg.arr]
            for fo, fo_url in feed_out:
                for fb, fb_url in feed_back:
                    trips.append(Trip(cabin, adults, join(fo.leg, o.leg), join(ret.leg, fb.leg), (
                        Ticket(fo.seller, tuple(s.code for s in fo.leg.segments), fo.total_eur, fo_url),
                        lh,
                        Ticket(fb.seller, tuple(s.code for s in fb.leg.segments), fb.total_eur, fb_url))))
    return trips
```

- [ ] **Step 4: Run the tests and check they pass.** `test_hub_pair...` expects 4 requests: long-haul stage 1, long-haul returns, feeder out, feeder back. Feeders are fetched only when a long-haul return is under budget. Self-transfer minimums and the 20-hour limit are checked later by `rules.check`.

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Build separate-ticket trips through hub airports"
```

---

### Task 10: Seating planner

**Files:**
- Create: `src/flightwatch/seating.py`
- Test: `tests/test_seating.py`

**Interfaces:**
- Produces:
  - `SeatPlan(groups: tuple[int, ...], seats: tuple[str, ...], windows: int, note: str)`
  - `plan_seats(layout: str, party: int) -> SeatPlan | None` (None for an unknown layout string)

Rules (spec, "Seating rules"):
- 4 people: all together if one block fits them. Otherwise 2 + 2 side by side across one aisle in the same row. Otherwise 3 + 1 across the aisle.
- 3 people: all together if a block fits them. Otherwise 2 + 1 across the aisle.
- Prefer a window block (first or last) when one fits everyone, for the view.

- [ ] **Step 1: Write failing tests** `tests/test_seating.py`
```python
from flightwatch.seating import plan_seats


def test_787_economy_four_is_two_plus_two_across_aisle():
    p = plan_seats("3-3-3", 4)
    assert p.groups == (2, 2) and p.seats == ("B", "C", "D", "E")


def test_three_take_a_window_block():
    p = plan_seats("3-3-3", 3)
    assert p.groups == (3,) and p.seats == ("A", "B", "C") and p.windows == 1


def test_middle_four_block_on_2_4_2():
    assert plan_seats("2-4-2", 4).seats == ("D", "E", "F", "G")


def test_premium_2_3_2_three_together_in_middle():
    assert plan_seats("2-3-2", 3).groups == (3,)


def test_premium_2_2_2_three_is_two_plus_one():
    assert plan_seats("2-2-2", 3).groups == (2, 1)


def test_narrowbody_four():
    assert plan_seats("3-3", 4).groups == (2, 2)


def test_unknown_layout():
    assert plan_seats("weird", 4) is None
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/seating.py`
```python
from dataclasses import dataclass

LETTERS = {
    "3-3-3": "ABC-DEF-HJK", "3-4-3": "ABC-DEFG-HJK", "2-4-2": "AC-DEFG-HK", "2-3-2": "AC-DEF-HK",
    "2-2-2": "AC-DF-HK", "3-3": "ABC-DEF", "2-2": "AC-DF", "2-3": "AC-DEF", "1-2-1": "A-DG-K",
}


@dataclass(frozen=True)
class SeatPlan:
    groups: tuple[int, ...]
    seats: tuple[str, ...]
    windows: int
    note: str


def plan_seats(layout: str, party: int) -> SeatPlan | None:
    spec = LETTERS.get(layout)
    if spec is None:
        return None
    blocks = [list(b) for b in spec.split("-")]
    n = len(blocks)
    window_seats = {blocks[0][0], blocks[-1][-1]}

    def plan(groups, seats, note):
        return SeatPlan(groups, tuple(seats), sum(1 for s in seats if s in window_seats), note)

    # 1) Everyone in one block, window blocks first
    for i in sorted(range(n), key=lambda i: (i not in (0, n - 1), i)):
        b = blocks[i]
        if len(b) >= party:
            seats = b[:party] if i == 0 else b[-party:] if i == n - 1 else b[:party]
            return plan((party,), seats, f"all {party} together, row-mates")
    # 2) Split across one aisle, same row: prefer pairs (2+2 or 2+1), then 3+1
    splits = [(2, party - 2), (party - 1, 1)] if party == 4 else [(party - 1, 1)]
    for left_n, right_n in splits:
        for i in range(n - 1):
            left, right = blocks[i], blocks[i + 1]
            if len(left) >= left_n and len(right) >= right_n:
                seats = left[-left_n:] + right[:right_n]
                return plan((left_n, right_n), seats, f"{left_n} + {right_n} in the same row, across the aisle")
    return None
```

- [ ] **Step 4: Run the tests and check they pass.**

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Plan seats so the family sits together"
```

---

### Task 11: Airline tables and enrichment

**Files:**
- Create: `src/flightwatch/data/airlines.toml`, `src/flightwatch/airlines.py`, `src/flightwatch/enrich.py`
- Test: `tests/test_airlines.py`, `tests/test_enrich.py`

**Interfaces:**
- Consumes: `Trip`, `Segment`, `Config`, `DaysOff`, `plan_seats`, `SeatPlan`, `rules.check`
- Produces:
  - `AirlineTable.load(path=None)`, `.get(code) -> Airline | None`, `.layout_for(code, aircraft, cabin) -> Layout | None`
  - `Airline(code, name, site, meals_longhaul, meals_shorthaul, paid_meal_eur, extra_legroom, extra_legroom_eur, exit_row_min_age, source, checked)`
  - `Layout(match, cabin, layout, pitch_in, width_in)`
  - `SegmentView(segment, layout, pitch_in, width_in, meals, seat_plan)`
  - `Result(trip, outbound, inbound, meal_addon_pp, price_pp, problems, school_days, recommended, extra_legroom, booking)`
  - `enrich(trip, cfg, airlines, cal) -> Result`

- [ ] **Step 1: Research and write `airlines.toml`.**
  - **Which airlines:** every carrier code in `tests/fixtures/*.html`, plus every airline in the TK, LO, LH, VL, OS, LX, NH, JL, EK, FZ, QR, EY, AZ, FB, AY, AF, KL, BA, PC, A3, CA, MU, KE, OZ list.
  - **Sources:** each airline's official pages: cabin and seat pages, meal pages, baggage pages, extra-legroom seat pages, and the exit-row age rule. Use aeroLOPA or SeatMaps only to cross-check layouts.
  - **Dating:** record the URL and today's date on every entry.
  - **Aircraft:** for each airline, record the aircraft types that appear on SOF or Tokyo routes, with an economy row and a premium-economy row where that cabin exists.
  - **Unknown values:** leave the key out. Code treats a missing value as "not verified".

  Format:
```toml
[LO]
name = "LOT Polish Airlines"
site = "https://www.lot.com"
meals_longhaul = "included"            # included | paid
meals_shorthaul = "snack"              # included | snack | paid
paid_meal_eur = 0                      # typical on-board meal price when paid
extra_legroom = "Extra Legroom seats (exit rows / bulkhead)"
extra_legroom_eur = [60, 120]          # typical per seat per long-haul flight
exit_row_min_age = 16
source = "https://www.lot.com/..."
checked = "2026-10-12"

[[LO.layouts]]
match = "787"                          # substring of Google's aircraft name
cabin = "economy"
layout = "3-3-3"
pitch_in = 31
width_in = 17.2

[[LO.layouts]]
match = "787"
cabin = "premium-economy"
layout = "2-3-2"
pitch_in = 38
width_in = 18.5
```

- [ ] **Step 2: Write failing tests**

`tests/test_airlines.py`:
```python
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
```

`tests/test_enrich.py`:
```python
from datetime import datetime, timedelta, date
from flightwatch.airlines import AirlineTable, Airline
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.enrich import enrich
from flightwatch.model import Leg, Segment, Ticket, Trip

CFG = load_config()
CAL = DaysOff((), date(2027, 6, 30), "test")


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
```

- [ ] **Step 3: Run them and watch them fail.**

- [ ] **Step 4: Implement** `src/flightwatch/airlines.py`
```python
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    match: str
    cabin: str
    layout: str
    pitch_in: float | None
    width_in: float | None


@dataclass(frozen=True)
class Airline:
    code: str
    name: str
    site: str
    meals_longhaul: str | None
    meals_shorthaul: str | None
    paid_meal_eur: float | None
    extra_legroom: str | None
    extra_legroom_eur: tuple[int, int] | None
    exit_row_min_age: int | None
    source: str
    checked: str
    layouts: tuple[Layout, ...]


class AirlineTable:
    def __init__(self, airlines: dict[str, Airline]):
        self.airlines = airlines

    @classmethod
    def load(cls, path: Path | None = None) -> "AirlineTable":
        text = path.read_text() if path else resources.files("flightwatch.data").joinpath("airlines.toml").read_text()
        out = {}
        for code, a in tomllib.loads(text).items():
            lays = tuple(Layout(l["match"], l["cabin"], l["layout"], l.get("pitch_in"), l.get("width_in"))
                         for l in a.get("layouts", []))
            ele = a.get("extra_legroom_eur")
            out[code] = Airline(code, a["name"], a["site"], a.get("meals_longhaul"), a.get("meals_shorthaul"),
                                a.get("paid_meal_eur"), a.get("extra_legroom"), tuple(ele) if ele else None,
                                a.get("exit_row_min_age"), a["source"], a["checked"], lays)
        return cls(out)

    def get(self, code: str) -> Airline | None:
        return self.airlines.get(code)

    def layout_for(self, code: str, aircraft: str, cabin: str) -> Layout | None:
        a = self.get(code)
        if a is None:
            return None
        for lay in a.layouts:
            if lay.cabin == cabin and lay.match.lower() in aircraft.lower():
                return lay
        return None
```

`src/flightwatch/enrich.py`:
```python
from dataclasses import dataclass

from flightwatch.airlines import AirlineTable
from flightwatch.model import Segment, Trip
from flightwatch.rules import check
from flightwatch.seating import SeatPlan, plan_seats

LONG_HAUL_MIN = 360     # 6 h or more counts as long-haul for meals and seat plans
MEAL_MIN = 120          # paid meals are added only on flights of 2 h or more


@dataclass(frozen=True)
class SegmentView:
    segment: Segment
    layout: str | None
    pitch_in: float | None
    width_in: float | None
    meals: str
    seat_plan: SeatPlan | None


@dataclass(frozen=True)
class Result:
    trip: Trip
    outbound: tuple[SegmentView, ...]
    inbound: tuple[SegmentView, ...]
    meal_addon_pp: float
    price_pp: float
    problems: tuple[str, ...]
    school_days: int
    recommended: bool
    extra_legroom: tuple[str, ...]
    booking: tuple[tuple[str, str], ...]


def _view(s: Segment, cabin: str, party: int, airlines: AirlineTable) -> tuple[SegmentView, float]:
    a = airlines.get(s.carrier)
    long_haul = s.minutes >= LONG_HAUL_MIN
    seg_cabin = cabin if long_haul else "economy"
    lay = airlines.layout_for(s.carrier, s.aircraft, seg_cabin)
    policy = None if a is None else (a.meals_longhaul if long_haul else a.meals_shorthaul)
    addon = 0.0
    if policy is None:
        meals = "not verified"
    elif policy == "paid":
        price = a.paid_meal_eur or 0
        meals = f"paid on board (~€{price:.0f})" if price else "paid on board"
        if s.minutes >= MEAL_MIN:
            addon = float(price)
    else:
        meals = policy
    plan = plan_seats(lay.layout, party) if lay else None
    return SegmentView(s, lay.layout if lay else None, lay.pitch_in if lay else None,
                       lay.width_in if lay else None, meals, plan), addon


def enrich(trip: Trip, cfg, airlines: AirlineTable, cal) -> Result:
    views, addon = {"out": [], "in": []}, 0.0
    for side, leg in (("out", trip.outbound), ("in", trip.inbound)):
        for s in leg.segments:
            v, a = _view(s, trip.cabin, trip.party, airlines)
            views[side].append(v)
            addon += a
    extra = []
    for code in dict.fromkeys(s.carrier for s in trip.outbound.segments + trip.inbound.segments):
        a = airlines.get(code)
        if a and a.extra_legroom:
            price = f" ~€{a.extra_legroom_eur[0]}–{a.extra_legroom_eur[1]} per seat per flight" if a.extra_legroom_eur else ""
            age = (f"; exit rows need age {a.exit_row_min_age}+, so not for the 14-year-old"
                   if a.exit_row_min_age and a.exit_row_min_age > 14 else "")
            extra.append(f"{a.name}: {a.extra_legroom}{price}{age}")
    booking = []
    for t in trip.tickets:
        a = airlines.get(t.seller)
        label = f"Book on {a.name} ({a.site})" if a else f"Book ({t.seller}; check it is sold by the airline)"
        booking.append((label, t.booking_url))
    problems = tuple(check(trip, cfg, addon))
    home = trip.inbound.arr.date()
    return Result(trip, tuple(views["out"]), tuple(views["in"]), addon, trip.per_person_eur + addon, problems,
                  cal.school_days_missed(trip.outbound.dep.date(), home),
                  trip.stay_days >= cfg.stay_recommended, tuple(extra), tuple(booking))
```

- [ ] **Step 5: Run the tests and check they pass.**
  - `test_school_days_and_recommended`: 5–20 Mar 2027 contains 11 weekdays (5, 8–12, 15–19 Mar); 20 Mar is a Saturday. The test calendar has no extra days off.
  - `test_unknown_airline_is_not_verified_but_kept`: the return leg here is 1,240 minutes, which `check` flags as a problem. The result is still returned, as Review Focus item 5 requires.

- [ ] **Step 6: Commit**
```bash
git add -A && git commit -m "Enrich trips with meals, legroom, seat plans and booking links"
```

---

### Task 12: Shard runner, encryption and merge

**Files:**
- Create: `src/flightwatch/crypto.py`, `src/flightwatch/shard.py`
- Test: `tests/test_shard.py`

**Interfaces:**
- Consumes: `date_pairs`, `shard`, `hub_pairs_today`, `search_pair_all_parties`, `search_hub_pair`, `GoogleClient`, `SearchFailed`, `BudgetExceeded`, `ConsentPageError`, `trip_to_dict`, `trip_from_dict`
- Produces:
  - `encrypt_json(obj, key: str) -> bytes`, `decrypt_json(data: bytes, key: str) -> object`, `new_key() -> str`
  - `Coverage(pairs_planned, pairs_done, hub_pairs_planned, hub_pairs_done, requests, failures: list[str], stopped_early: bool, shards_seen: int, shards_expected: int)`, with `.merge(other)` and the property `.complete -> bool`
  - `ShardResult(trips, coverage)`
  - `run_shard(client, cfg, today, index, total, limit_days: int | None = None) -> ShardResult`
  - `save_shard(res, path, key)`
  - `merge_shards(paths, key, expected) -> ShardResult`

- [ ] **Step 1: Write failing tests** `tests/test_shard.py`
```python
from datetime import date
from googlefake import FakeTransport, page, CONSENT
from flightwatch.config import load_config
from flightwatch.crypto import new_key, encrypt_json, decrypt_json
from flightwatch.google.client import GoogleClient
from flightwatch.shard import run_shard, save_shard, merge_shards, Coverage
from dataclasses import replace

CFG = replace(load_config(), hubs=())


def test_crypto_round_trip():
    k = new_key()
    assert decrypt_json(encrypt_json({"a": 1}, k), k) == {"a": 1}


def test_shard_with_no_flights_is_complete_and_empty():
    cfg = replace(CFG, horizon_months=0, lead_days=0)          # window = today only: 13 pairs × 2 cabins
    t = FakeTransport([(200, page([]))] * 26)
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    assert res.trips == [] and res.coverage.pairs_planned == 26 and res.coverage.pairs_done == 26


def test_failures_are_recorded_and_consent_stops_shard():
    cfg = replace(CFG, horizon_months=0, lead_days=0)
    t = FakeTransport([(200, CONSENT)])
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    assert res.coverage.stopped_early and "consent" in res.coverage.failures[0].lower()
    assert not res.coverage.complete


def test_merge_flags_missing_shards(tmp_path):
    k = new_key()
    cfg = replace(CFG, horizon_months=0, lead_days=0)
    t = FakeTransport([(200, page([]))] * 26)
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    save_shard(res, tmp_path / "shard-0.bin", k)
    merged = merge_shards([tmp_path / "shard-0.bin"], k, expected=2)
    assert merged.coverage.shards_seen == 1 and not merged.coverage.complete
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement**

`src/flightwatch/crypto.py`:
```python
import json

from cryptography.fernet import Fernet


def new_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_json(obj, key: str) -> bytes:
    return Fernet(key.encode()).encrypt(json.dumps(obj).encode())


def decrypt_json(data: bytes, key: str):
    return json.loads(Fernet(key.encode()).decrypt(data))
```

`src/flightwatch/shard.py`:
```python
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from flightwatch.crypto import decrypt_json, encrypt_json
from flightwatch.dates import date_pairs, hub_pairs_today, shard
from flightwatch.google.client import BudgetExceeded, SearchFailed
from flightwatch.google.parse import ConsentPageError
from flightwatch.model import Trip, trip_from_dict, trip_to_dict
from flightwatch.search import search_pair_all_parties
from flightwatch.selftransfer import search_hub_pair


@dataclass
class Coverage:
    pairs_planned: int = 0
    pairs_done: int = 0
    hub_pairs_planned: int = 0
    hub_pairs_done: int = 0
    requests: int = 0
    failures: list[str] = field(default_factory=list)
    stopped_early: bool = False
    shards_seen: int = 1
    shards_expected: int = 1

    @property
    def complete(self) -> bool:
        return (not self.stopped_early and self.shards_seen == self.shards_expected
                and self.pairs_done == self.pairs_planned and self.hub_pairs_done == self.hub_pairs_planned)

    def merge(self, o: "Coverage") -> None:
        for f in ("pairs_planned", "pairs_done", "hub_pairs_planned", "hub_pairs_done", "requests"):
            setattr(self, f, getattr(self, f) + getattr(o, f))
        self.failures += o.failures
        self.stopped_early |= o.stopped_early


@dataclass
class ShardResult:
    trips: list[Trip]
    coverage: Coverage


def run_shard(client, cfg, today: date, index: int, total: int, limit_days: int | None = None) -> ShardResult:
    all_pairs = date_pairs(today, cfg, limit_days)
    pairs = shard(all_pairs, total, index)
    hub_pairs = shard(hub_pairs_today(all_pairs, today, cfg.hub_rotation_days), total, index)
    cabins = list(cfg.budget_pp_eur)
    cov = Coverage(pairs_planned=len(pairs) * len(cabins),
                   hub_pairs_planned=len(hub_pairs) * len(cabins) * len(cfg.hubs))
    trips: list[Trip] = []
    try:
        for d, r in pairs:
            for cabin in cabins:
                try:
                    trips += search_pair_all_parties(client, cfg, d, r, cabin)
                    cov.pairs_done += 1
                except SearchFailed as e:
                    cov.failures.append(f"{cabin} {d}→{r}: {e}")
        cache: dict = {}
        for hub in cfg.hubs:
            for d, r in hub_pairs:
                for cabin in cabins:
                    try:
                        for adults in cfg.parties:
                            trips += search_hub_pair(client, cfg, hub, d, r, cabin, adults, cache)
                        cov.hub_pairs_done += 1
                    except SearchFailed as e:
                        cov.failures.append(f"hub {hub} {cabin} {d}→{r}: {e}")
    except ConsentPageError as e:
        cov.stopped_early = True
        cov.failures.insert(0, f"Google consent page: {e}")
    except BudgetExceeded as e:
        cov.stopped_early = True
        cov.failures.insert(0, f"request budget reached: {e}")
    cov.requests = client.requests
    return ShardResult(trips, cov)


def save_shard(res: ShardResult, path: Path, key: str) -> None:
    path.write_bytes(encrypt_json({"trips": [trip_to_dict(t) for t in res.trips],
                                   "coverage": asdict(res.coverage)}, key))


def merge_shards(paths: list[Path], key: str, expected: int) -> ShardResult:
    trips: list[Trip] = []
    cov = Coverage(shards_seen=0, shards_expected=expected)
    for p in paths:
        data = decrypt_json(Path(p).read_bytes(), key)
        trips += [trip_from_dict(t) for t in data["trips"]]
        cov.merge(Coverage(**{k: v for k, v in data["coverage"].items() if k not in ("shards_seen", "shards_expected")}))
        cov.shards_seen += 1
    if cov.shards_seen < expected:
        cov.failures.insert(0, f"{expected - cov.shards_seen} of {expected} search jobs produced no results")
    return ShardResult(trips, cov)
```

- [ ] **Step 4: Run the tests and check they pass.**

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Run a search shard, encrypt its results and merge shards"
```

---

### Task 13: Price history and trends

**Files:**
- Create: `src/flightwatch/history.py`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: `encrypt_json`, `decrypt_json`
- Produces:
  - `load(path, key) -> dict`
  - `save(path, key, hist)`
  - `record(hist, entries: list[tuple[str, float]], today) -> None`
  - `record_best(hist, cabin, party, best_pp: float | None, today)`
  - `trend(hist, key) -> str`

- [ ] **Step 1: Write failing tests** `tests/test_history.py`
```python
from datetime import date
from flightwatch.crypto import new_key
from flightwatch.history import load, save, record, trend, record_best


def test_missing_file_is_empty(tmp_path):
    assert load(tmp_path / "h.bin", new_key()) == {}


def test_record_and_trend(tmp_path):
    k, h = new_key(), {}
    record(h, [("A", 1150.0)], date(2026, 10, 12))
    assert trend(h, "A") == "new today"
    record(h, [("A", 1100.0)], date(2026, 10, 13))
    assert trend(h, "A") == "down €50 since 2026-10-12"
    save(tmp_path / "h.bin", k, h)
    assert load(tmp_path / "h.bin", k) == h


def test_same_day_rerun_replaces_value():
    h = {}
    record(h, [("A", 1150.0)], date(2026, 10, 12))
    record(h, [("A", 1140.0)], date(2026, 10, 12))
    assert h["trips"]["A"] == [["2026-10-12", 1140]]


def test_best_per_day_series():
    h = {}
    record_best(h, "economy", 4, 1180.4, date(2026, 10, 12))
    assert h["best"]["economy|4"] == [["2026-10-12", 1180]]
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/history.py`
```python
from datetime import date, timedelta
from pathlib import Path

from flightwatch.crypto import decrypt_json, encrypt_json

KEEP_DAYS = 60


def load(path: Path, key: str) -> dict:
    p = Path(path)
    return decrypt_json(p.read_bytes(), key) if p.exists() else {}


def save(path: Path, key: str, hist: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(encrypt_json(hist, key))


def _put(series: list, today: date, value: int) -> None:
    if series and series[-1][0] == today.isoformat():
        series[-1][1] = value
    else:
        series.append([today.isoformat(), value])


def record(hist: dict, entries: list[tuple[str, float]], today: date) -> None:
    trips = hist.setdefault("trips", {})
    for key, pp in entries:
        _put(trips.setdefault(key, []), today, round(pp))
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for key in [k for k, s in trips.items() if s[-1][0] < cutoff]:
        del trips[key]


def record_best(hist: dict, cabin: str, party: int, best_pp: float | None, today: date) -> None:
    if best_pp is not None:
        _put(hist.setdefault("best", {}).setdefault(f"{cabin}|{party}", []), today, round(best_pp))


def trend(hist: dict, key: str) -> str:
    s = hist.get("trips", {}).get(key, [])
    if len(s) < 2:
        return "new today"
    (d0, prev), (_, now) = s[-2], s[-1]
    if now == prev:
        return f"same as {d0}"
    return f"{'down' if now < prev else 'up'} €{abs(now - prev):,} since {d0}"
```

- [ ] **Step 4: Run the tests and check they pass.**

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Keep encrypted price history and show trends"
```

---

### Task 14: HTML report and email content

**Files:**
- Create: `src/flightwatch/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Result`, `Coverage`, `history.trend`, `DaysOff.source`
- Produces:
  - `rank(results) -> list[Result]`: qualifying results first, then by school days, then by price
  - `render_html(results, cov, today, hist, calendar_source) -> str`
  - `render_email(results, cov, today, hist) -> tuple[str, str, str]`: subject, text body, HTML body

**Report content** (spec, "Report contents"). Each row shows:
- cabin, party size, dates, stay (with a recommended tag), school days missed;
- outbound and return: each flight's code, airline, aircraft, airports, local departure and arrival with weekday, layover minutes and total time;
- the arrival time in Tokyo and the arrival time home in Sofia;
- price per person and in total, the meal add-on, and "23 kg bag included";
- legroom (Google's figure, plus pitch and width from the table), the layout and seat plan for long-haul flights, and window count;
- meals per flight;
- extra-legroom options with prices;
- self-transfer warnings;
- the trend;
- booking links.

**Controls:** sorting by clicking a column header, and filters for cabin, party, recommended stay only, maximum school days, through-tickets only, and "leaves Fri/Sat or a day off".

**Coverage banner at the top:** "Checked X of Y date pairs (Z%) with N requests". It lists failures. When coverage is incomplete it reads "INCOMPLETE: some dates were not checked, so missing results do not mean no deals".

- [ ] **Step 1: Write failing tests** `tests/test_report.py`
```python
from datetime import date, datetime, timedelta
from flightwatch.airlines import AirlineTable
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.enrich import enrich
from flightwatch.model import Leg, Segment, Ticket, Trip
from flightwatch.report import render_html, render_email, rank
from flightwatch.shard import Coverage

CFG = load_config()
CAL = DaysOff((), date(2027, 6, 30), "https://mon.bg/x")


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
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Implement** `src/flightwatch/report.py`
```python
from datetime import date
from html import escape

from flightwatch.enrich import Result, SegmentView
from flightwatch.history import trend


def rank(results: list[Result]) -> list[Result]:
    return sorted(results, key=lambda r: (bool(r.problems), r.school_days, r.price_pp))


def _eur(x: float) -> str:
    return f"€{x:,.0f}"


def _hm(m: int) -> str:
    return f"{m // 60}h{m % 60:02d}"


def _pct(cov) -> int:
    planned = cov.pairs_planned + cov.hub_pairs_planned
    return 100 if planned == 0 else round(100 * (cov.pairs_done + cov.hub_pairs_done) / planned)


def _coverage_line(cov) -> str:
    line = (f"Checked {cov.pairs_done:,} of {cov.pairs_planned:,} date pairs and "
            f"{cov.hub_pairs_done:,} of {cov.hub_pairs_planned:,} hub pairs ({_pct(cov)}%) with {cov.requests:,} requests.")
    if not cov.complete:
        line = "INCOMPLETE: some dates were not checked, so missing results do not mean no deals. " + line
    return line


def _seg_html(v: SegmentView) -> str:
    s = v.segment
    leg = f"{s.dep:%a %d %b %H:%M} {s.origin} → {s.arr:%a %d %b %H:%M} {s.destination}"
    legroom = escape(s.legroom or "legroom n/a")
    table = (f", {v.pitch_in:g}\" pitch" if v.pitch_in else "") + (f", {v.width_in:g}\" wide" if v.width_in else "")
    seats = ""
    if v.seat_plan:
        seats = f"<br><small>Seats ({v.layout}): {' '.join(v.seat_plan.seats)}, {v.seat_plan.note}, {v.seat_plan.windows} window</small>"
    elif v.segment.minutes >= 360:
        seats = "<br><small>Seat plan: layout not verified</small>"
    return (f"<div><b>{escape(s.code)}</b> {escape(s.airline)}, {escape(s.aircraft)}<br>{escape(leg)} ({_hm(s.minutes)})"
            f"<br><small>Legroom {legroom}{table}. Meals: {escape(v.meals)}</small>{seats}</div>")


def _leg_html(views, leg) -> str:
    parts = []
    for i, v in enumerate(views):
        parts.append(_seg_html(v))
        if i < len(leg.layovers):
            parts.append(f"<div class=lay>Connection at {escape(v.segment.destination)}: {_hm(leg.layovers[i])}</div>")
    parts.append(f"<div class=tot>Door to door {_hm(leg.minutes)}</div>")
    return "".join(parts)


def _row(r: Result, hist: dict) -> str:
    t = r.trip
    ok = not r.problems
    off = t.outbound.dep.weekday() in (4, 5)
    links = " ".join(f"<a href=\"{escape(u)}\">{escape(label)}</a>" for label, u in r.booking)
    warn = "".join(f"<li>{escape(p)}</li>" for p in r.problems)
    if t.self_transfer:
        warn += "<li>Separate tickets: if the first flight is late, the next airline will not rebook you.</li>"
    extra = "".join(f"<li>{escape(e)}</li>" for e in r.extra_legroom) or "<li>not verified</li>"
    return f"""<tr class="{'ok' if ok else 'near'}" data-cabin="{t.cabin}" data-party="{t.party}" data-school="{r.school_days}"
 data-rec="{int(r.recommended)}" data-st="{int(t.self_transfer)}" data-off="{int(off)}" data-price="{r.price_pp:.0f}">
<td data-v="{r.price_pp:.0f}"><b>{_eur(r.price_pp)}</b> pp<br>{_eur(r.price_pp * t.party)} total for {t.party}<br>
<small>23 kg bag included{', meals add ' + _eur(r.meal_addon_pp) + ' pp' if r.meal_addon_pp else ''}</small><br><small>{escape(trend(hist, t.key))}</small></td>
<td data-v="{t.outbound.dep:%Y%m%d}">{t.cabin.replace('-', ' ')}<br>{t.outbound.dep:%a %d %b} → {t.inbound.arr:%a %d %b %Y}<br>
<b>{t.stay_days} days</b> in Japan{' (recommended)' if r.recommended else ''}</td>
<td data-v="{r.school_days}">{r.school_days}</td>
<td>{_leg_html(r.outbound, t.outbound)}<div class=arr>Arrive Tokyo {t.outbound.arr:%a %d %b %H:%M}</div></td>
<td>{_leg_html(r.inbound, t.inbound)}<div class=arr>Arrive Sofia {t.inbound.arr:%a %d %b %H:%M}</div></td>
<td><ul>{extra}</ul></td>
<td>{links}<ul class=warn>{warn}</ul></td></tr>"""


STYLE = """
:root{--bg:#fff;--fg:#111;--mut:#666;--ok:#e8f6ec;--near:#fff6e0;--line:#ddd;--acc:#0b57d0}
@media (prefers-color-scheme: dark){:root{--bg:#111;--fg:#eee;--mut:#aaa;--ok:#12301c;--near:#33280c;--line:#333;--acc:#8ab4f8}}
body{background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,system-ui,sans-serif;margin:16px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}
th{cursor:pointer;position:sticky;top:0;background:var(--bg)}tr.ok{background:var(--ok)}tr.near{background:var(--near)}
small,.lay,.tot{color:var(--mut)}.arr{font-weight:600;margin-top:4px}a{color:var(--acc)}.warn{color:#b3261e}
.banner{padding:10px;border:1px solid var(--line);margin-bottom:12px}.filters label{margin-right:12px}
"""

SCRIPT = """
const rows=[...document.querySelectorAll('tbody tr')];
function apply(){const f=id=>document.getElementById(id);
 rows.forEach(r=>{let show=true;
  if(f('cabin').value&&r.dataset.cabin!==f('cabin').value)show=false;
  if(f('party').value&&r.dataset.party!==f('party').value)show=false;
  if(f('rec').checked&&r.dataset.rec!=='1')show=false;
  if(f('through').checked&&r.dataset.st==='1')show=false;
  if(f('off').checked&&r.dataset.off!=='1')show=false;
  if(f('ok').checked&&!r.classList.contains('ok'))show=false;
  if(f('school').value!==''&&+r.dataset.school>+f('school').value)show=false;
  r.style.display=show?'':'none';});}
document.querySelectorAll('.filters input,.filters select').forEach(e=>e.addEventListener('input',apply));
document.querySelectorAll('th[data-sort]').forEach((th,i)=>th.addEventListener('click',()=>{
 const tb=document.querySelector('tbody'),col=[...th.parentNode.children].indexOf(th),dir=th.dataset.dir=th.dataset.dir==='1'?'-1':'1';
 rows.sort((a,b)=>(+a.children[col].dataset.v-+b.children[col].dataset.v)*dir).forEach(r=>tb.appendChild(r));}));
apply();
"""


def render_html(results: list[Result], cov, today: date, hist: dict, calendar_source: str) -> str:
    ranked = rank(results)
    failures = "".join(f"<li>{escape(f)}</li>" for f in cov.failures[:50])
    body = "".join(_row(r, hist) for r in ranked) or "<tr><td colspan=7>No trips within 10% of budget.</td></tr>"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Sofia–Tokyo flights</title><style>{STYLE}</style></head><body>
<h1>Sofia ↔ Tokyo, {today:%d %b %Y}</h1>
<div class=banner>{escape(_coverage_line(cov))}<ul>{failures}</ul>
<small>Prices from Google Flights (cheapest seller). The airline's own price can be a little higher; open the link to check.
Green rows are under budget (economy €1,200 / premium economy €1,300 per person, 23 kg bag included); yellow rows are within 10%.
School days use the official calendar: {escape(calendar_source)}. All of December counts as off.</small></div>
<div class=filters><label>Cabin <select id=cabin><option value="">all</option><option value=economy>economy</option>
<option value=premium-economy>premium economy</option></select></label>
<label>People <select id=party><option value="">all</option><option>4</option><option>3</option></select></label>
<label><input type=checkbox id=ok checked> under budget only</label>
<label><input type=checkbox id=rec> 14+ days only</label>
<label><input type=checkbox id=through> one ticket only</label>
<label><input type=checkbox id=off> leaves Fri/Sat</label>
<label>Max school days <input id=school type=number min=0 style="width:4em"></label></div>
<table><thead><tr><th data-sort>Price</th><th data-sort>Dates</th><th data-sort>School days</th><th>Outbound</th>
<th>Return</th><th>Extra legroom</th><th>Book</th></tr></thead><tbody>{body}</tbody></table>
<script>{SCRIPT}</script></body></html>"""


def _line(r: Result) -> str:
    t = r.trip
    codes = "+".join(s.code for s in t.outbound.segments) + " / " + "+".join(s.code for s in t.inbound.segments)
    return (f"{_eur(r.price_pp)} pp ({_eur(r.price_pp * t.party)} for {t.party}), {t.cabin.replace('-', ' ')}, "
            f"{t.outbound.dep:%a %d %b} → {t.inbound.arr:%a %d %b}, {t.stay_days} days, {r.school_days} school days, {codes}")


def render_email(results: list[Result], cov, today: date, hist: dict) -> tuple[str, str, str]:
    ranked = rank(results)
    deals = [r for r in ranked if not r.problems]
    if not cov.complete:
        subject = f"SOF–TYO: INCOMPLETE search ({_pct(cov)}% checked), {len(deals)} deal(s) found so far"
    elif deals:
        best = deals[0]
        subject = (f"SOF–TYO: {len(deals)} deal{'s' if len(deals) != 1 else ''} under budget, "
                   f"best {_eur(best.price_pp)} pp, {best.school_days} school days")
    else:
        cheapest = min((r.price_pp for r in ranked), default=None)
        subject = "SOF–TYO: no deals under budget today" + (f" (closest {_eur(cheapest)} pp)" if cheapest else "")
    top = deals[:10] or ranked[:5]
    text = "\n".join([_coverage_line(cov), *cov.failures[:10], "", *(_line(r) for r in top), "",
                      "Full report attached (open report.html)."])
    html = (f"<p>{escape(_coverage_line(cov))}</p><ol>"
            + "".join(f"<li>{escape(_line(r))} <a href=\"{escape(r.booking[0][1])}\">book</a></li>" for r in top)
            + "</ol><p>Full report attached.</p>")
    return subject, text, html
```

- [ ] **Step 4: Run the tests and check they pass.**

- [ ] **Step 5: Commit**
```bash
git add -A && git commit -m "Render the HTML report and daily email"
```

---

### Task 15: CLI, email sending, and a live smoke run

**Files:**
- Create: `src/flightwatch/notify.py`, `src/flightwatch/cli.py`, `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces the console command `flightwatch`, with these subcommands:
  - `shard --index I --total N --out FILE [--limit-days D]`
  - `report --shards DIR --history FILE --out report.html [--no-email]`
  - `local [--limit-days D] [--no-email] [--history FILE]`: runs every shard in one process, then the report
  - `fallback-check --repo OWNER/NAME`: exit 0 if today's GitHub run succeeded, exit 1 otherwise
- Environment variables:
  - `FLIGHTWATCH_KEY`, required
  - `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO`; if any is missing, the email step prints the subject and skips sending

- [ ] **Step 1: Write a failing test** `tests/test_cli.py`. It runs the whole pipeline offline with a fake transport.
```python
import base64
from datetime import date
from googlefake import page, itin, seg
from flightwatch import cli
from flightwatch.crypto import new_key

OUT = itin("TK", [seg("SOF", "IST", [2027, 1, 24], [9, 30], [2027, 1, 24], [12], 90, "TK", "1"),
                  seg("IST", "NRT", [2027, 1, 24], [15, 25], [2027, 1, 25], [8, 40], 675, "TK", "50")], 970, [205], 4400)
RET = itin("TK", [seg("NRT", "IST", [2027, 2, 8], [10], [2027, 2, 8], [17], 780, "TK", "51"),
                  seg("IST", "SOF", [2027, 2, 8], [20], [2027, 2, 8], [21, 30], 90, "TK", "2")], 1050, [180], 4400)


def transport(params):
    # Stage-2 queries carry selected segments, which name IST; stage-1 queries only name SOF and TYO
    return 200, page([RET]) if b"IST" in base64.b64decode(params["tfs"]) else page([OUT])


def test_local_pipeline_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIGHTWATCH_KEY", new_key())
    monkeypatch.setattr(cli, "make_transport", lambda: transport)
    monkeypatch.setattr(cli, "today", lambda: date(2027, 1, 10))
    report = tmp_path / "report.html"
    cli.main(["local", "--limit-days", "1", "--no-email", "--no-hubs", "--interval", "0",
              "--history", str(tmp_path / "h.bin"), "--out", str(report)])
    html = report.read_text()
    assert "TK50" in html and "100%" in html
    assert (tmp_path / "h.bin").exists()
```

- [ ] **Step 2: Run it and watch it fail.**

- [ ] **Step 3: Implement**

`src/flightwatch/notify.py`:
```python
import os
import smtplib
from email.message import EmailMessage


def send_email(subject: str, text: str, html: str, attachment_html: str) -> bool:
    user, password, to = (os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "MAIL_TO"))
    if not (user and password and to):
        print("email not configured; subject would be:", subject)
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(attachment_html.encode(), maintype="text", subtype="html", filename="report.html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.send_message(msg)
    return True
```

`src/flightwatch/cli.py`:
```python
import argparse
import json
import os
import sys
import urllib.request
from dataclasses import replace
from datetime import date
from pathlib import Path

from flightwatch import history
from flightwatch.airlines import AirlineTable
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.dates import today_in
from flightwatch.enrich import enrich
from flightwatch.google.client import GoogleClient, primp_transport
from flightwatch.notify import send_email
from flightwatch.report import render_email, render_html
from flightwatch.shard import ShardResult, merge_shards, run_shard, save_shard


def make_transport():
    return primp_transport()


def today() -> date:
    return today_in(load_config().timezone)


def _key() -> str:
    key = os.environ.get("FLIGHTWATCH_KEY")
    if not key:
        sys.exit("FLIGHTWATCH_KEY is not set")
    return key


def _search(args, day: date, index: int, total: int) -> ShardResult:
    cfg = load_config()
    if args.no_hubs:
        cfg = replace(cfg, hubs=())
    client = GoogleClient(transport=make_transport(), min_interval=args.interval,
                          max_requests=cfg.max_requests_per_run // total)
    return run_shard(client, cfg, day, index, total, args.limit_days)


def _report(res: ShardResult, args, day: date) -> None:
    cfg, key = load_config(), _key()
    airlines, cal = AirlineTable.load(), DaysOff.load()
    results = [enrich(t, cfg, airlines, cal) for t in res.trips]

    def fits_rules(r):
        return not [p for p in r.problems if "budget" not in p]

    shown = [r for r in results if fits_rules(r) and r.price_pp <= cfg.budget_pp_eur[r.trip.cabin] * cfg.stage2_margin]
    hist = history.load(Path(args.history), key)
    history.record(hist, [(r.trip.key, r.price_pp) for r in shown], day)
    for cabin in cfg.budget_pp_eur:
        for party in cfg.parties:
            prices = [r.price_pp for r in results if fits_rules(r) and r.trip.cabin == cabin and r.trip.party == party]
            history.record_best(hist, cabin, party, min(prices, default=None), day)
    html = render_html(shown, res.coverage, day, hist, cal.source)
    Path(args.out).write_text(html)
    subject, text, body = render_email(shown, res.coverage, day, hist)
    print(subject)
    if not args.no_email:
        send_email(subject, text, body, html)
    history.save(Path(args.history), key, hist)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="flightwatch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    shard_p, local_p, report_p = sub.add_parser("shard"), sub.add_parser("local"), sub.add_parser("report")
    for p in (shard_p, local_p):
        p.add_argument("--limit-days", type=int)
        p.add_argument("--no-hubs", action="store_true")
        p.add_argument("--interval", type=float, default=1.0)
    for p in (local_p, report_p):
        p.add_argument("--history", default="history/history.bin")
        p.add_argument("--no-email", action="store_true")
        p.add_argument("--out", default="report.html")
    shard_p.add_argument("--index", type=int, required=True)
    shard_p.add_argument("--total", type=int, required=True)
    shard_p.add_argument("--out", required=True)
    report_p.add_argument("--shards", required=True)
    report_p.add_argument("--expected", type=int, default=16)
    fc = sub.add_parser("fallback-check")
    fc.add_argument("--repo", required=True)
    args = ap.parse_args(argv)
    day = today()

    if args.cmd == "shard":
        save_shard(_search(args, day, args.index, args.total), Path(args.out), _key())
    elif args.cmd == "local":
        _report(_search(args, day, 0, 1), args, day)
    elif args.cmd == "report":
        paths = sorted(Path(args.shards).glob("shard-*.bin"))
        _report(merge_shards(paths, _key(), args.expected), args, day)
    elif args.cmd == "fallback-check":
        url = (f"https://api.github.com/repos/{args.repo}/actions/workflows/daily.yml/runs"
               f"?status=success&created=%3E%3D{day.isoformat()}")
        with urllib.request.urlopen(url, timeout=30) as r:
            sys.exit(0 if json.load(r).get("total_count", 0) > 0 else 1)


if __name__ == "__main__":
    main()
```

`README.md` must cover:
- what the tool does, in a few lines;
- the cost rule;
- how to read the report;
- one-time setup:
  - `python -c "from flightwatch.crypto import new_key; print(new_key())"`, then save the output as the GitHub secret `FLIGHTWATCH_KEY` and keep a copy in the macOS Keychain;
  - a Gmail app password (Google Account → Security → 2-Step Verification → App passwords), saved as `GMAIL_APP_PASSWORD`;
  - `GMAIL_USER` and `MAIL_TO` both set to kamenlevi@gmail.com;
- how to run a local test: `flightwatch local --limit-days 2 --no-email`;
- how the Mac fallback works.

- [ ] **Step 4: Run all the tests and check they pass.** Run `.venv/bin/pytest -q`.

- [ ] **Step 5: Live smoke run.** This is a real Google search over the first 2 departure dates: 26 date pairs × 2 cabins, plus follow-ups, which is about 60–120 requests at 1 per second. No email is sent.
```bash
FLIGHTWATCH_KEY=$(.venv/bin/python -c "from flightwatch.crypto import new_key; print(new_key())") \
  .venv/bin/flightwatch local --limit-days 2 --no-email --no-hubs --history /tmp/fw-smoke.bin --out report.html
```
Expected:
- a subject line is printed;
- `report.html` opens in a browser;
- the coverage banner shows 100%;
- any trips show Turkish, LOT, Lufthansa and so on, with legroom, times and booking links that open the matching Google booking page.

Check one result by hand on Google Flights: same dates, 4 adults, 1 checked bag. The price should match within a few euros.

- [ ] **Step 6: Commit**
```bash
git add -A && git commit -m "Add CLI, email sending and README"
```

---

### Task 16: GitHub repo and daily workflow

**Files:**
- Create: `.github/workflows/daily.yml`, `history/.gitkeep`

**Interfaces:**
- Consumes: the CLI (Task 15) and the secrets `FLIGHTWATCH_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO`

- [ ] **Step 1: Write the workflow** `.github/workflows/daily.yml`
```yaml
name: daily
on:
  schedule:
    - cron: "0 3 * * *"        # 06:00 Sofia (05:00 in winter)
  workflow_dispatch: {}
permissions:
  contents: write
concurrency:
  group: daily
  cancel-in-progress: false
jobs:
  shard:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    strategy:
      fail-fast: false
      matrix:
        index: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install .
      - run: flightwatch shard --index ${{ matrix.index }} --total 16 --out shard-${{ matrix.index }}.bin
        env:
          FLIGHTWATCH_KEY: ${{ secrets.FLIGHTWATCH_KEY }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: shard-${{ matrix.index }}
          path: shard-${{ matrix.index }}.bin
          retention-days: 2
          if-no-files-found: ignore
  report:
    needs: shard
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install .
      - uses: actions/download-artifact@v4
        with:
          path: shards
          pattern: shard-*
          merge-multiple: true
      - run: flightwatch report --shards shards --history history/history.bin --out report.html --expected 16
        env:
          FLIGHTWATCH_KEY: ${{ secrets.FLIGHTWATCH_KEY }}
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          MAIL_TO: ${{ secrets.MAIL_TO }}
      # The daily commit also keeps the repo active, so GitHub does not disable the schedule after 60 idle days
      - run: |
          git config user.name "flightwatch"
          git config user.email "flightwatch@users.noreply.github.com"
          git add history/history.bin
          git commit -m "History $(date -u +%F)" || echo "no change"
          git push
```

- [ ] **Step 2: Create the public repo and push.** Kamen approved a public repo on 2026-10-11. First check that no file in the repo holds a secret:
```bash
git grep -nE "app.?password|FLIGHTWATCH_KEY=|BEGIN .*PRIVATE" -- . ':!README.md' ':!.github' ; echo "grep exit: $?"
gh repo create kamenlevi/sofia-tokyo-flights --public --source . --push --description "Daily Sofia–Tokyo flight price watch"
```
Expected: grep finds nothing (exit 1), then the repo is created and pushed.

- [ ] **Step 3: Kamen adds the secrets.** Claude can't enter passwords, so stop and ask Kamen to set the 4 secrets. The UI path is Settings → Secrets and variables → Actions. Alternatively, Kamen can paste each value in his own terminal:
```bash
gh secret set FLIGHTWATCH_KEY --repo kamenlevi/sofia-tokyo-flights
gh secret set GMAIL_USER --repo kamenlevi/sofia-tokyo-flights
gh secret set GMAIL_APP_PASSWORD --repo kamenlevi/sofia-tokyo-flights
gh secret set MAIL_TO --repo kamenlevi/sofia-tokyo-flights
```
Wait until Kamen says they are set. Check with `gh secret list --repo kamenlevi/sofia-tokyo-flights`, which shows names only.

- [ ] **Step 4: First full run, started by hand.**
```bash
gh workflow run daily --repo kamenlevi/sofia-tokyo-flights
```
After the run, read the job summary with `gh run view --repo kamenlevi/sofia-tokyo-flights`. Expected:
- all 16 shard jobs and the report job are green;
- the email arrives, its coverage line reads 100%, and report.html is attached;
- `history/history.bin` is committed.

If shards hit the 60-minute timeout or the request budget, the email says INCOMPLETE. In that case raise `shards` (config and the matrix list together) rather than the per-request interval.

- [ ] **Step 5: Commit any fixes, then push.**

---

### Task 17: Mac backup runner

**Files:**
- Create: `mac/fallback.sh`, `mac/com.kamen.flightwatch.plist`
- Modify: `README.md` (install steps)

- [ ] **Step 1: Write** `mac/fallback.sh`
```bash
#!/bin/zsh
# Runs at noon. If today's GitHub run did not succeed, search from this Mac instead.
set -u
REPO_DIR="$HOME/sofia-tokyo-flights"
cd "$REPO_DIR" || exit 1
export PATH="$REPO_DIR/.venv/bin:/usr/bin:/bin"
if flightwatch fallback-check --repo kamenlevi/sofia-tokyo-flights; then
  echo "$(date) GitHub run OK, nothing to do"; exit 0
fi
export FLIGHTWATCH_KEY="$(security find-generic-password -s flightwatch-key -w)"
export GMAIL_USER="$(security find-generic-password -s flightwatch-gmail-user -w)"
export GMAIL_APP_PASSWORD="$(security find-generic-password -s flightwatch-gmail-app-password -w)"
export MAIL_TO="$GMAIL_USER"
git pull --ff-only
caffeinate -i flightwatch local --history history/history.bin --out report.html
git add history/history.bin && git commit -m "History $(date +%F) (Mac fallback)" && git push
```

- [ ] **Step 2: Write** `mac/com.kamen.flightwatch.plist`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kamen.flightwatch</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string>
    <string>$HOME/sofia-tokyo-flights/mac/fallback.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/flightwatch.log</string>
  <key>StandardErrorPath</key><string>/tmp/flightwatch.log</string>
</dict></plist>
```
launchd runs a missed `StartCalendarInterval` job when the Mac next wakes, so a sleeping Mac still catches up.

- [ ] **Step 3: Install it** (Claude can do this; it only touches the user's LaunchAgents):
```bash
chmod +x mac/fallback.sh
cp mac/com.kamen.flightwatch.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kamen.flightwatch.plist
```

- [ ] **Step 4: Kamen stores 3 Keychain items** in his own terminal; each command prompts for the value:
```bash
security add-generic-password -s flightwatch-key -a "$USER" -w
security add-generic-password -s flightwatch-gmail-user -a "$USER" -w
security add-generic-password -s flightwatch-gmail-app-password -a "$USER" -w
```

- [ ] **Step 5: Test the check path.** Run `launchctl kickstart gui/$(id -u)/com.kamen.flightwatch && sleep 5 && tail /tmp/flightwatch.log`. Expected after a successful GitHub run that day: "GitHub run OK, nothing to do".

- [ ] **Step 6: Commit and push**
```bash
git add -A && git commit -m "Add the Mac backup runner" && git push
```
