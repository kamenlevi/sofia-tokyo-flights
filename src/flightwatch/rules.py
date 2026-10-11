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
