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
            lh = Ticket(o.seller if o.seller == ret.seller else "multi", tuple(s.code for s in o.leg.segments + ret.leg.segments), ret.total_eur, lh_url)
            feed_back = [(f, u) for f, u in _feeders(client, cfg, hub, cfg.origin, ret.leg.arr.date(), adults, cache)
                         if f.leg.dep > ret.leg.arr]
            for fo, fo_url in feed_out:
                for fb, fb_url in feed_back:
                    trips.append(Trip(cabin, adults, join(fo.leg, o.leg), join(ret.leg, fb.leg), (
                        Ticket(fo.seller, tuple(s.code for s in fo.leg.segments), fo.total_eur, fo_url),
                        lh,
                        Ticket(fb.seller, tuple(s.code for s in fb.leg.segments), fb.total_eur, fb_url))))
    return trips
