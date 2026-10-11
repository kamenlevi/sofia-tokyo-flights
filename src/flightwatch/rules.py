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


LONG_HAUL_MIN = 360


def budget_cabin(trip: Trip) -> str:
    """The premium economy budget applies only if every long-haul flight really is premium economy."""
    if trip.cabin == "premium-economy":
        for s in trip.outbound.segments + trip.inbound.segments:
            if s.minutes >= LONG_HAUL_MIN and s.cabin is not None and s.cabin < 2:
                return "economy"
    return trip.cabin


def check(trip: Trip, cfg, addon_pp: float = 0.0) -> list[str]:
    p = structural_problems(trip, cfg)
    cabin = budget_cabin(trip)
    budget = cfg.budget_pp_eur[cabin]
    if price_pp(trip, addon_pp) > budget:
        label = "economy" if cabin != trip.cabin else ""
        p.append(f"€{price_pp(trip, addon_pp):,.0f} per person is over the €{budget:,} {label + ' ' if label else ''}budget"
                 + (" (a long-haul flight is economy, not premium economy)" if label else ""))
    return p
