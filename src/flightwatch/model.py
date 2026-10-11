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
