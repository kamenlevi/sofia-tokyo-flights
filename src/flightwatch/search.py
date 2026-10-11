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
