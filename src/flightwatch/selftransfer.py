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
    return _hub_pair(client, cfg, hub, d, r, cabin, adults, cache)[0]


def search_hub_pair_all_parties(client, cfg, hub: str, d: date, r: date, cabin: str, cache: FeederCache) -> list[Trip]:
    """Same rule as through-fares: search 3 people when 4 found nothing or came within budget × party_b_margin."""
    big, small = cfg.parties
    trips, min_pp = _hub_pair(client, cfg, hub, d, r, cabin, big, cache)
    if min_pp is None or min_pp <= cfg.budget_pp_eur[cabin] * cfg.party_b_margin:
        trips += _hub_pair(client, cfg, hub, d, r, cabin, small, cache)[0]
    return trips


def _hub_pair(client, cfg, hub, d, r, cabin, adults, cache) -> tuple[list[Trip], float | None]:
    budget = cfg.budget_pp_eur[cabin]

    def legs(sel_out=(), sel_ret=()):
        return [LegQuery(d.isoformat(), hub, cfg.destination, sel_out), LegQuery(r.isoformat(), cfg.destination, hub, sel_ret)]

    stage1 = [o for o in client.search(build_params(legs(), cabin, adults, 0, None, cfg.checked_bags))
              if o.total_eur is not None]
    min_pp = min((o.total_eur for o in stage1), default=None)
    min_pp = None if min_pp is None else min_pp / adults
    outs = [o for o in stage1 if o.total_eur / adults <= budget]
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
            lh = Ticket(o.seller if o.seller == ret.seller else "multi", tuple(s.code for s in o.leg.segments + ret.leg.segments), ret.total_eur, lh_url)
            feed_back = [(f, u) for f, u in _feeders(client, cfg, hub, cfg.origin, ret.leg.arr.date(), adults, cache)
                         if f.leg.dep > ret.leg.arr]
            for fo, fo_url in feed_out:
                for fb, fb_url in feed_back:
                    trips.append(Trip(cabin, adults, join(fo.leg, o.leg), join(ret.leg, fb.leg), (
                        Ticket(fo.seller, tuple(s.code for s in fo.leg.segments), fo.total_eur, fo_url),
                        lh,
                        Ticket(fb.seller, tuple(s.code for s in fb.leg.segments), fb.total_eur, fb_url))))
    return trips, min_pp
