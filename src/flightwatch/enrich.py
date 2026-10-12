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
    days: object = None               # DayBreakdown from leaving Sofia to getting home

    @property
    def japan_nights(self) -> int:
        return self.trip.stay_days

    @property
    def japan_full_days(self) -> int:
        """Days in Japan not counting the day you land and the day you leave."""
        return max(self.trip.stay_days - 1, 0)


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
                  trip.stay_days >= cfg.stay_recommended, tuple(extra), tuple(booking),
                  cal.breakdown(trip.outbound.dep.date(), home))
